# Models used by the webcam sensors

| File | What | Source |
|---|---|---|
| `emotion_yolo11n_cls.onnx` | Facial-emotion classifier (YOLO11n-cls, 8 classes), run with onnxruntime | trained here: [emotion_model/](../emotion_model/README.md) |
| `emotion_yolo11n_cls.json` | Its class names, input size and held-out test metrics | written by `emotion_model/train.py` |
| `emotion_yolo11n_cls.pt` | The same model as ultralytics weights (for fine-tuning; not needed at run time) | written by `emotion_model/train.py` |
| `face_landmarker.task` | MediaPipe FaceLandmarker (478 landmarks incl. irises), used by EyeTrax for gaze features and by us for the face crop | [Google MediaPipe](https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task) |

If `face_landmarker.task` is missing, download it from the link above into this folder (3.7 MB).
