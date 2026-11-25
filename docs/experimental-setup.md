# Experimental setup

Use the same laptop, room and settings for every participant; webcam emotion and gaze estimates are sensitive to lighting
and position.

## Room

| Item | Setting | Why |
|---|---|---|
| Lighting | Even light on the face; no bright window or lamp behind the participant | The face model needs a well-lit, unshadowed face |
| Background | Plain, no other faces (posters, people walking by) | The camera should see one face |
| Noise | Quiet, notifications off | Distractions change expressions |
| Researcher | Out of the participant's view, not talking | Being watched changes behaviour |

## Laptop and webcam

- Built-in or USB webcam at the top of the screen, facing the participant; 640 × 480 at 30 fps is enough
  (`config/devices.yaml → camera`).
- Participant about an arm's length (50–70 cm) from the screen, face centred. Glasses are fine; avoid caps or hair over the eyes.
- Windows display scaling 100 %, browser fullscreen (kiosk mode, opened by the app). Gaze is calibrated for the full screen.
- Close every other app that could use the camera.
- Check with `python run.py camera`: the face box should be stable and the emotion label plausible (q to quit).

## What the sensors do

| Stream | How | File |
|---|---|---|
| Facial emotion | MediaPipe finds the face; our YOLO11n classifier (trained on RAF-DB + AffectNet, 73.8 % test accuracy) gives 8 expression probabilities, plus valence/arousal, about 10 times a second | `emotion.csv` |
| Gaze | EyeTrax (MediaPipe eye landmarks + a ridge model fitted in the 9-dot calibration at the start); accuracy is roughly 3–6 cm, enough to tell which answer block is being looked at | `gaze.csv` |

Video frames are processed in memory and **never saved**. Both streams use the session's master clock, so they line up with
every click and look change.

## Configuration

- `config/genui.yaml`: looks, queries, timings, the switch rule (`adaptation`), calibration points.
- `config/devices.yaml`: camera index and the two webcam sensors; `--sensors mock` / `--sensors off` override it.
