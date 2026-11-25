"""Webcam sensing: one camera, one processing thread, two recorders.

    CameraHub        opens the webcam (OpenCV) and runs MediaPipe FaceLandmarker on every frame through
                     EyeTrax's GazeEstimator, so each frame yields the face box *and* the gaze features.
    WebcamGaze       (eye_tracker: webcam)  EyeTrax gaze estimation, calibrated by the existing on-screen
                     calibration step (/api/calibration/*). Writes gaze.csv.
    YoloEmotion      (emotion: yolo)        crops the face and runs our YOLO11n classifier (ONNX) trained on
                     RAF-DB + AffectNet (emotion_model/). Writes emotion.csv.

Every row is stamped with the master clock at frame capture, so it lines up with events, mouse and markers.
No video is saved: frames are processed in memory and discarded.
"""

import json
import threading
import time
from pathlib import Path

import numpy as np

from .. import paths
from ..clock import now
from .base import EyeSensor, Sensor, SensorError

# Approximate position of each basic emotion on Russell's circumplex (valence, arousal in -1..1).
# Used to turn the classifier's probabilities into continuous valence / arousal estimates.
CIRCUMPLEX = {
    "anger": (-0.60, 0.65), "contempt": (-0.50, 0.25), "disgust": (-0.65, 0.35), "fear": (-0.60, 0.75),
    "happy": (0.80, 0.45), "neutral": (0.00, 0.00), "sad": (-0.70, -0.40), "surprise": (0.15, 0.80),
}


def _resolve(p):
    p = Path(p)
    return p if p.is_absolute() else paths.ROOT / p


class CameraHub:
    """Shared by the webcam sensors of one session (keyed by camera index)."""

    _hubs = {}
    _hubs_lock = threading.Lock()

    @classmethod
    def get(cls, options):
        options = options or {}
        key = options.get("index", 0)
        with cls._hubs_lock:
            if key not in cls._hubs:
                cls._hubs[key] = cls(options)
            return cls._hubs[key]

    def __init__(self, options):
        self.options = options
        self.sensors = []
        self.thread = None
        self.cap = None
        self.estimator = None
        self.error = None
        self.frames = 0
        self.fps = 0.0
        self.latest = None            # (t, frame, face_box) for the live monitor
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._ready = threading.Event()

    # -- lifecycle -------------------------------------------------------
    def attach(self, sensor):
        with self._lock:
            if sensor not in self.sensors:
                self.sensors.append(sensor)
            if self.thread is None:
                self._open()

    def detach(self, sensor):
        with self._lock:
            if sensor in self.sensors:
                self.sensors.remove(sensor)
            last = not self.sensors
        if last:
            self.close()

    def _open(self):
        try:
            import cv2
        except ImportError:
            raise SensorError("opencv-python is not installed: pip install -r requirements.txt")
        face_model = _resolve(self.options.get("face_landmarker", "models/face_landmarker.task"))
        if not face_model.exists():
            raise SensorError(f"MediaPipe face model missing: {paths.rel(face_model)} (see models/README.md)")
        try:
            from eyetrax import GazeEstimator
        except ImportError:
            raise SensorError("eyetrax is not installed: pip install -r requirements.txt")
        index = self.options.get("index", 0)
        backend = cv2.CAP_DSHOW if self.options.get("dshow", False) else cv2.CAP_ANY   # ANY opens much faster here
        cap = cv2.VideoCapture(index, backend)
        if not cap.isOpened():
            cap = cv2.VideoCapture(index)
        if not cap.isOpened():
            raise SensorError(f"Webcam {index} could not be opened (in use by another app, or blocked in "
                              f"Windows Settings > Privacy > Camera?)")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.options.get("width", 640))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.options.get("height", 480))
        cap.set(cv2.CAP_PROP_FPS, self.options.get("fps", 30))
        ok, frame = cap.read()
        if not ok or frame is None:
            cap.release()
            raise SensorError(f"Webcam {index} opened but delivered no image")
        self.cap = cap
        self.size = (frame.shape[1], frame.shape[0])
        self.estimator = GazeEstimator(model_name="ridge", model_kwargs={"alpha": self.options.get("ridge_alpha", 1.0)},
                                       face_landmarker_model=str(face_model))
        self.estimator._face_landmarker = _Recorder(self.estimator._face_landmarker)
        self._stop.clear()
        self.thread = threading.Thread(target=self._run, name="webcam", daemon=True)
        self.thread.start()

    def close(self):
        self._stop.set()
        if self.thread is not None:
            self.thread.join(timeout=3)
        if self.cap is not None:
            self.cap.release()
        if self.estimator is not None:
            try:
                self.estimator.close()
            except Exception:
                pass
        self.thread = self.cap = self.estimator = None
        with CameraHub._hubs_lock:
            for k, v in list(CameraHub._hubs.items()):
                if v is self:
                    del CameraHub._hubs[k]

    # -- processing ------------------------------------------------------
    def _run(self):
        mirror = self.options.get("mirror", False)
        window = []
        while not self._stop.is_set():
            ok, frame = self.cap.read()
            t = now()
            if not ok or frame is None:
                self.error = "camera read failed"
                time.sleep(0.05)
                continue
            if mirror:
                frame = frame[:, ::-1].copy()
            try:
                features, blink = self.estimator.extract_features(frame)
                box = self._face_box(frame.shape)
            except Exception as exc:     # one bad frame must not stop the recording
                self.error = f"landmarks: {exc}"
                features, blink, box = None, False, None
            self.latest = (t, frame, box)
            self.frames += 1
            window = [x for x in window if x > t - 2] + [t]
            self.fps = (len(window) - 1) / max(window[-1] - window[0], 1e-6) if len(window) > 1 else 0.0
            for s in list(self.sensors):
                try:
                    s.on_frame(t, frame, features, bool(blink), box)
                except Exception as exc:
                    s.error = str(exc)

    def _face_box(self, shape):
        """Square face crop (pixels) around the landmarks, enlarged like the training crops; None without a face."""
        res = self.estimator._face_landmarker.last
        if res is None or not res.face_landmarks:
            return None
        h, w = shape[:2]
        pts = np.array([(lm.x * w, lm.y * h) for lm in res.face_landmarks[0]], dtype=np.float32)
        x0, y0 = pts.min(0)
        x1, y1 = pts.max(0)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        side = max(x1 - x0, y1 - y0) * self.options.get("face_margin", 1.0)
        return (int(cx - side / 2), int(cy - side / 2), int(cx + side / 2), int(cy + side / 2))


class _Recorder:
    """Wraps EyeTrax's FaceLandmarker so the hub can reuse the landmarks of the same pass for the face box."""

    def __init__(self, inner):
        self.inner = inner
        self.last = None

    def detect_for_video(self, image, ts):
        self.last = self.inner.detect_for_video(image, ts)
        return self.last

    def close(self):
        self.inner.close()


def crop_square(frame, box, size):
    """Crop box from frame (zero-padded where it leaves the image) and resize to size x size, RGB."""
    import cv2
    x0, y0, x1, y1 = box
    h, w = frame.shape[:2]
    pad = max(0, -x0, -y0, x1 - w, y1 - h)
    if pad:
        frame = cv2.copyMakeBorder(frame, pad, pad, pad, pad, cv2.BORDER_CONSTANT)
        x0, y0, x1, y1 = x0 + pad, y0 + pad, x1 + pad, y1 + pad
    face = frame[y0:y1, x0:x1]
    face = cv2.resize(face, (size, size), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(face, cv2.COLOR_BGR2RGB)


class EmotionClassifier:
    """The trained YOLO11n-cls model, run with onnxruntime (no torch needed at session time)."""

    def __init__(self, model_path):
        model_path = _resolve(model_path)
        meta_path = model_path.with_suffix(".json")
        if not model_path.exists():
            raise SensorError(f"Emotion model missing: {paths.rel(model_path)} (train it: emotion_model/README.md)")
        try:
            import onnxruntime as ort
        except ImportError:
            raise SensorError("onnxruntime is not installed: pip install -r requirements.txt")
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2          # leave the CPU to the browser and the landmarker
        self.session = ort.InferenceSession(str(model_path), opts, providers=["CPUExecutionProvider"])
        self.input = self.session.get_inputs()[0].name
        self.imgsz = meta.get("imgsz") or self.session.get_inputs()[0].shape[-1]
        self.classes = meta.get("classes") or list(CIRCUMPLEX)
        self.meta = meta

    def predict(self, face_rgb):
        x = face_rgb.astype(np.float32).transpose(2, 0, 1)[None] / 255.0
        p = self.session.run(None, {self.input: x})[0][0].astype(float)
        if p.min() < 0 or abs(p.sum() - 1) > 1e-3:      # logits: apply softmax
            e = np.exp(p - p.max())
            p = e / e.sum()
        return p


def valence_arousal(classes, probs):
    va = np.array([CIRCUMPLEX.get(c, (0.0, 0.0)) for c in classes])
    v, a = (np.asarray(probs)[:, None] * va).sum(0)
    return float(v), float(a)


class YoloEmotion(Sensor):
    kind = "emotion"
    adapter = "yolo"
    flush_s = 0.5
    dynamic_columns = True

    def _start(self):
        self.model = EmotionClassifier(self.options.get("model", "models/emotion_yolo11n_cls.onnx"))
        self.classes = self.model.classes
        self.columns = ["t", "face", "face_x0", "face_y0", "face_x1", "face_y1", "emotion", "confidence",
                        *[f"p_{c}" for c in self.classes], "valence", "arousal"]
        self.open_stream()
        self.period = 1.0 / float(self.options.get("hz", 10))
        self._next = 0.0
        self.smooth = None                       # EMA of probabilities, for the live display only
        self.live = {"face": False, "emotion": "", "confidence": 0.0, "valence": 0.0, "arousal": 0.0}
        self.nominal_hz = float(self.options.get("hz", 10))
        self.info = {"model": paths.rel(_resolve(self.options.get("model", "models/emotion_yolo11n_cls.onnx"))),
                     "classes": self.classes, "imgsz": self.model.imgsz,
                     "test_top1": (self.model.meta.get("test") or {}).get("top1")}
        self.hub = CameraHub.get(self.options.get("camera"))
        self.hub.attach(self)

    def _stop(self):
        if getattr(self, "hub", None):
            self.hub.detach(self)

    def on_frame(self, t, frame, features, blink, box):
        if t < self._next:
            return
        self._next = t + self.period
        h, w = frame.shape[:2]
        if box is None:
            self.live.update(face=False)
            self.emit([t, 0, "", "", "", "", "", "", *[""] * len(self.classes), "", ""])
            return
        probs = self.model.predict(crop_square(frame, box, self.model.imgsz))
        k = int(np.argmax(probs))
        v, a = valence_arousal(self.classes, probs)
        x0, y0, x1, y1 = box
        self.emit([t, 1, round(x0 / w, 4), round(y0 / h, 4), round(x1 / w, 4), round(y1 / h, 4),
                   self.classes[k], round(float(probs[k]), 4), *[round(float(p), 4) for p in probs],
                   round(v, 4), round(a, 4)])
        alpha = float(self.options.get("display_smoothing", 0.6))
        self.smooth = probs if self.smooth is None else alpha * self.smooth + (1 - alpha) * probs
        ks = int(np.argmax(self.smooth))
        sv, sa = valence_arousal(self.classes, self.smooth)
        self.live = {"face": True, "emotion": self.classes[ks], "confidence": float(self.smooth[ks]),
                     "valence": sv, "arousal": sa, "probs": dict(zip(self.classes, map(float, self.smooth)))}

    def status(self):
        s = super().status()
        if getattr(self, "hub", None) and self.hub.error and not s["error"]:
            s["error"] = self.hub.error
        return s


class WebcamGaze(EyeSensor):
    """EyeTrax webcam gaze. Before calibration rows carry face/blink only (valid = 0)."""

    adapter = "webcam"
    columns = ["t", "x", "y", "valid", "blink", "face", "x_raw", "y_raw"]

    def _start(self):
        self.calibrated = False
        self._collect = None                 # (x, y, until) while a calibration point is being recorded
        self._samples = []                   # [(features, (x, y))]
        self._ema = None
        self.alpha = float(self.options.get("smoothing", 0.6))
        self.hub = CameraHub.get(self.options.get("camera"))
        self.hub.attach(self)
        self.nominal_hz = self.options.get("camera", {}).get("fps", 30)
        self.info = {"library": "EyeTrax (MediaPipe FaceLandmarker + ridge regression)"}
        self.live = None
        # the calibrated model is kept in the session folder so --resume does not need a new calibration
        self.model_file = self.store.folder / "gaze_model.pkl"
        if self.model_file.exists():
            try:
                self.hub.estimator.load_model(self.model_file)
                self.calibrated = True
            except Exception as exc:
                self.error = f"saved gaze model unusable: {exc}"

    def _stop(self):
        if getattr(self, "hub", None):
            self.hub.detach(self)

    def on_frame(self, t, frame, features, blink, box):
        face = int(features is not None)
        c = self._collect
        if c is not None and features is not None and not blink and t <= c[2]:
            self._samples.append((features, (c[0], c[1])))
        if not face or not self.calibrated:
            self.emit([t, "", "", 0, int(blink), face, "", ""])
            return
        rx, ry = (float(v) for v in self.hub.estimator.predict(np.asarray([features]))[0])
        if blink:          # eyes closed: keep the last estimate, mark invalid
            self.emit([t, "", "", 0, 1, 1, round(rx, 4), round(ry, 4)])
            return
        if self._ema is None:
            self._ema = (rx, ry)
        else:
            a = self.alpha
            self._ema = (a * self._ema[0] + (1 - a) * rx, a * self._ema[1] + (1 - a) * ry)
        x, y = (min(1.1, max(-0.1, v)) for v in self._ema)
        self.live = (x, y)
        self.emit([t, round(x, 4), round(y, 4), 1, 0, 1, round(rx, 4), round(ry, 4)])

    # -- calibration (driven by web/shell/js/steps/calibration.js) --------
    def calibration_start(self):
        self.calibrated = False        # no predictions while the model is being (re)fitted
        self._samples = []
        self._collect = None

    def calibration_point(self, x, y):
        before = len(self._samples)
        self._collect = (float(x), float(y), now() + float(self.options.get("point_seconds", 0.8)))
        time.sleep(float(self.options.get("point_seconds", 0.8)) + 0.05)
        self._collect = None
        return len(self._samples) - before >= 5

    def calibration_compute(self):
        targets = {xy for _, xy in self._samples}
        if len(targets) < 5:
            if self.model_file.exists():          # keep the previous attempt's model rather than none
                self.hub.estimator.load_model(self.model_file)
                self.calibrated = True
            return {"status": "failure", "points": len(targets), "samples": len(self._samples)}
        X = np.asarray([f for f, _ in self._samples])
        Y = np.asarray([xy for _, xy in self._samples])
        self.hub.estimator.train(X, Y)
        self.calibrated = True
        try:
            self.hub.estimator.save_model(self.model_file)
        except Exception:
            pass
        self._ema = None
        return {"status": "success", "points": len(targets), "samples": len(self._samples)}

    def calibration_stop(self):
        self._collect = None

    def gaze_since(self, since):
        return [(r[0], r[1], r[2]) for r in self.recent(since) if r[3] == 1]


class MockEmotion(Sensor):
    """Simulated emotion stream for dry runs without a webcam (probabilities drift with the phase's arousal)."""

    kind = "emotion"
    adapter = "mock"
    nominal_hz = 10
    flush_s = 0.5
    classes = list(CIRCUMPLEX)
    columns = ["t", "face", "face_x0", "face_y0", "face_x1", "face_y1", "emotion", "confidence",
               *[f"p_{c}" for c in CIRCUMPLEX], "valence", "arousal"]

    def _start(self):
        import random
        self.rng = random.Random(11)
        self.live = {"face": True, "emotion": "neutral", "confidence": 0.0, "valence": 0.0, "arousal": 0.0}
        self._thread = threading.Thread(target=self._run, name="mock-emotion", daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop_event.wait(1.0 / self.nominal_hz):
            a = self.context.arousal
            if now() < getattr(self.context, "force_negative_until", 0.0):     # simulated frown (pilot hotkey)
                w = np.array([0.9, 0.2, 0.3, 0.2, 0.02, 0.15, 1.1, 0.1])
            else:
                w = np.array([0.4 * a, 0.1, 0.1, 0.3 * a, 0.6 - 0.4 * a, 1.0, 0.3, 0.3 * a])
            w = w + np.array([self.rng.random() * 0.3 for _ in self.classes])
            p = w / w.sum()
            k = int(np.argmax(p))
            v, ar = valence_arousal(self.classes, p)
            self.live = {"face": True, "emotion": self.classes[k], "confidence": float(p[k]), "valence": v,
                         "arousal": ar, "probs": dict(zip(self.classes, map(float, p)))}
            self.emit([now(), 1, 0.4, 0.3, 0.6, 0.6, self.classes[k], round(float(p[k]), 4),
                       *[round(float(x), 4) for x in p], round(v, 4), round(ar, 4)])
