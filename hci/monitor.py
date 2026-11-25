"""Annotated webcam view for the researcher: face box, emotion probabilities, valence/arousal and gaze.

Used by  /monitor            (MJPEG stream while a session runs; open it on the researcher's screen)
and      python run.py camera (stand-alone live demo of the emotion model, no session).
"""

import time

import cv2
import numpy as np

COLORS = {"anger": (60, 60, 230), "contempt": (40, 130, 200), "disgust": (60, 160, 90), "fear": (170, 90, 160),
          "happy": (40, 200, 240), "neutral": (170, 170, 170), "sad": (200, 120, 50), "surprise": (230, 160, 230)}


def annotate(frame, box, live_emotion=None, gaze=None, fps=None):
    img = frame.copy()
    h, w = img.shape[:2]
    e = live_emotion or {}
    if box is not None:
        color = COLORS.get(e.get("emotion"), (255, 255, 255))
        cv2.rectangle(img, box[:2], box[2:], color, 2)
        if e.get("emotion"):
            label = f"{e['emotion']} {e.get('confidence', 0):.0%}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            y = max(box[1], th + 8)
            cv2.rectangle(img, (box[0], y - th - 8), (box[0] + tw + 8, y), color, -1)
            cv2.putText(img, label, (box[0] + 4, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
    else:
        cv2.putText(img, "no face", (12, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 80, 255), 2)

    # probability bars
    probs = e.get("probs") or {}
    panel = np.full((h, 230, 3), 32, np.uint8)
    y = 24
    cv2.putText(panel, "emotion (YOLO11n)", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)
    for name, p in sorted(probs.items(), key=lambda kv: -kv[1]):
        y += 24
        cv2.putText(panel, name, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)
        cv2.rectangle(panel, (90, y - 11), (90 + int(120 * p), y - 1), COLORS.get(name, (200, 200, 200)), -1)
    if probs:
        y += 34
        cv2.putText(panel, f"valence {e.get('valence', 0):+.2f}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)
        y += 22
        cv2.putText(panel, f"arousal {e.get('arousal', 0):+.2f}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)
        # circumplex mini-plot
        cx, cy, r = 115, y + 70, 55
        cv2.circle(panel, (cx, cy), r, (90, 90, 90), 1)
        cv2.line(panel, (cx - r, cy), (cx + r, cy), (70, 70, 70), 1)
        cv2.line(panel, (cx, cy - r), (cx, cy + r), (70, 70, 70), 1)
        px, py = int(cx + r * e.get("valence", 0)), int(cy - r * e.get("arousal", 0))
        cv2.circle(panel, (px, py), 5, (40, 200, 240), -1)
        y = cy + r + 20

    # gaze: where on the participant's screen (mini screen)
    sw, sh = 200, 112
    x0, y0 = 15, min(h - sh - 30, y + 10)
    cv2.putText(panel, "gaze (EyeTrax)", (x0, y0 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)
    cv2.rectangle(panel, (x0, y0), (x0 + sw, y0 + sh), (120, 120, 120), 1)
    if gaze is not None:
        gx, gy = gaze
        cv2.circle(panel, (int(x0 + sw * min(1, max(0, gx))), int(y0 + sh * min(1, max(0, gy)))), 6, (60, 220, 60), -1)
    else:
        cv2.putText(panel, "not calibrated", (x0 + 40, y0 + 60), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 150), 1)
    if fps:
        cv2.putText(img, f"{fps:.0f} fps", (w - 80, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 255, 200), 1)
    return np.hstack([img, panel])


def mjpeg(sensing, hz=12):
    from .sensors.webcam import CameraHub
    while True:
        hub = next(iter(CameraHub._hubs.values()), None)
        live = sensing.live()
        if hub is None or hub.latest is None:
            img = np.full((480, 870, 3), 40, np.uint8)
            cv2.putText(img, "waiting for webcam...", (30, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (200, 200, 200), 2)
        else:
            _, frame, box = hub.latest
            img = annotate(frame, box, live.get("emotion"), live.get("gaze"), hub.fps)
        ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if ok:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n"
        time.sleep(1 / hz)
        if sensing.sensors and all(s._stop_event.is_set() for s in sensing.sensors.values()):
            return


def thumb_mjpeg(sensing, width=240, hz=10):
    """Small mirrored webcam thumbnail with the face box, for the pilot-only demo overlay."""
    from .sensors.webcam import CameraHub
    while True:
        hub = next(iter(CameraHub._hubs.values()), None)
        if hub is not None and hub.latest is not None:
            _, frame, box = hub.latest
            img = frame.copy()
            e = sensing.live().get("emotion") or {}
            if box is not None:
                cv2.rectangle(img, box[:2], box[2:], COLORS.get(e.get("emotion"), (255, 255, 255)), 3)
            img = img[:, ::-1]                                  # mirror: feels natural to the person on camera
            h = int(img.shape[0] * width / img.shape[1])
            img = cv2.resize(np.ascontiguousarray(img), (width, h), interpolation=cv2.INTER_AREA)
            ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n"
        time.sleep(1 / hz)
        if sensing.sensors and all(s._stop_event.is_set() for s in sensing.sensors.values()):
            return


def camera_demo(devices):
    """Stand-alone live window: webcam + YOLO emotion (+ landmarks). Esc or q quits."""
    from .clock import now
    from .sensors.webcam import CameraHub, EmotionClassifier, crop_square, valence_arousal

    class _Probe:
        error = None

        def __init__(self, model):
            self.model, self.smooth, self.live = model, None, {}

        def on_frame(self, t, frame, features, blink, box):
            if box is None:
                self.live = {}
                return
            p = self.model.predict(crop_square(frame, box, self.model.imgsz))
            self.smooth = p if self.smooth is None else 0.6 * self.smooth + 0.4 * p
            k = int(np.argmax(self.smooth))
            v, a = valence_arousal(self.model.classes, self.smooth)
            self.live = {"emotion": self.model.classes[k], "confidence": float(self.smooth[k]), "valence": v,
                         "arousal": a, "probs": dict(zip(self.model.classes, map(float, self.smooth)))}

    emo_cfg = (devices.get("emotion") or {}).get("yolo") or {}
    probe = _Probe(EmotionClassifier(emo_cfg.get("model", "models/emotion_yolo11n_cls.onnx")))
    cam = dict(devices.get("camera") or {})
    cam.setdefault("mirror", True)
    hub = CameraHub.get(cam)
    hub.attach(probe)
    try:
        while True:
            if hub.latest is not None:
                _, frame, box = hub.latest
                cv2.imshow("Emotion model live demo (q to quit)", annotate(frame, box, probe.live, None, hub.fps))
            if cv2.waitKey(30) & 0xFF in (27, ord("q")):
                break
    finally:
        hub.detach(probe)
        cv2.destroyAllWindows()
