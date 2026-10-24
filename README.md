# Emotion-Adaptive Menus: Trial Platform

This platform runs a full experimental session with one command. It induces an emotion, has the participant complete website tasks, records eye tracking, GSR, heart rate and behaviour on one shared clock, and saves everything as model-ready data.

This is **phase 1** of the project, which collects labelled data. Every participant uses one standard drop-down menu. The model trained on this data will drive the adaptive menus in phase 2.

| Group | Emotions | Website (our own; information architecture modelled on WebArena, Zhou et al. 2024) |
|---|---|---|
| **G1** | Stress vs Calm | Northfield University student portal |
| **G2** | Frustration vs Boredom | Everyday Market online store |
| **G3** | Joy (amusement) vs Sadness | Threadline discussion forum |

Every participant does **both** emotions of their group. The order of the emotions and of the two task sets is counterbalanced automatically.

---

## Quick start

```powershell
pip install -r requirements.txt                       # once (plus the device libraries you need)
python run.py check                                   # sensors, videos, browser: must say "Ready."
python run.py session --group G2 --participant P04    # run one participant
```

`session` does the following:
1. Starts the sensors and checks that each one delivers data.
2. Opens a fullscreen kiosk browser.
3. Guides the participant through the session (about 40 minutes).
4. Saves everything to `data/G2/P04/`.

The terminal shows the current phase, live sensor rates and any warnings.

| Command | What it does |
|---|---|
| `python run.py check [--group G1] [--mock]` | Checks packages, config, task answers, videos, port, browser and sensors |
| `python run.py session --group G1 --participant P01` | Runs a real session |
| `… --mock --fast --pilot` | Dry run: simulated sensors, short timings, saved in `data/_pilot/` |
| `… --resume` | Continues an interrupted session from its last unfinished step |
| `… --windowed` / `--no-browser` | Normal browser window / don't open a browser |
| `python run.py preview --group G3` | Lets you browse a group's website without recording anything |
| `python run.py export` | Combines all sessions into `data/exports/` |
| `python run.py clean-pilot` | Deletes `data/_pilot/` |
| `python -m pytest` | Runs the automated tests (a simulated participant walks a whole session) |

To stop a session, press **Ctrl+C** in the terminal or **Ctrl+Shift+Q** in the browser. Both save what was recorded so far.

## Before the first real participant

1. **Sensors.** Set the GSR and heart-rate adapters in [config/devices.yaml](config/devices.yaml) (they start as `unset`) and install the matching library. Details are in [docs/experimental-setup.md](docs/experimental-setup.md).
2. **Videos.** The calm and neutral clips are already installed. For G3, add the two film clips (`amusement.mp4`, `sadness.mp4`) as described in [stimuli/README.md](stimuli/README.md).
3. **Forms.** Fill in the bracketed contact and ethics details in [docs/consent-form.md](docs/consent-form.md).
4. **Dry run.** Do a full run on yourself with `--pilot` and the real hardware.

## What a session looks like

```
consent → demographics → eye-tracker calibration → 3 min rest (baseline) → mood rating
→ Block 1: induction → mood rating → 6 min website tasks → mood rating + workload (NASA-TLX)
→ neutral video (washout) → mood rating
→ Block 2: same, with the other emotion and the other task set
→ debrief (with the option to withdraw) → thank you
```

## Output per participant: `data/<group>/<participant>/`

| File | Contents |
|---|---|
| `session.json` | Group, counterbalancing plan, devices, screen size, calibration quality, status |
| `markers.csv` | Start and end of every phase; these are the labels |
| `gaze.csv` | Tobii gaze points (0–1 screen coordinates), pupil sizes, validity |
| `gsr.csv`, `hr.csv` | Skin conductance (µS); heart rate (BPM) and RR intervals |
| `events.csv` | Every click, menu open/close/hover, page view, sabotage event, key press |
| `mouse.csv` | Mouse position at up to 60 Hz |
| `aoi.csv` | On-screen rectangles of menu items, page content and the task bar, for gaze mapping |
| `tasks.csv` | One row per task: outcome, time, clicks, menu opens, wrong pages, … |
| `questionnaires.csv` | Consent, demographics, SAM, emotion ratings, NASA-TLX, debrief choice |
| `merged.csv` | **The model-ready table:** 10 Hz timeline with phase, emotion and task labels plus all signals |

Every column is described in [docs/data-dictionary.md](docs/data-dictionary.md).

## Project layout

```
run.py              the single entry point
config/             groups, emotions, timings, devices, task sets   ← edit here
hci/                Python: session flow, server, sensors, export
web/shell/          what the participant sees (consent, inductions, ratings, task screen)
web/core/           shared website engine (menu, pages, logging)
web/sites/          the three websites (site.json content + theme.css)
stimuli/            video clips + the neutral-clip generator (see stimuli/README.md)
docs/               setup, protocol, consent, debrief, rationale, data dictionary
tests/              automated tests
data/               created by the first session; results only
```

## Documentation

- [docs/experimental-setup.md](docs/experimental-setup.md): room, hardware, sensor placement, PC settings
- [docs/protocol.md](docs/protocol.md): step-by-step researcher script and participant schedule
- [docs/emotion-induction.md](docs/emotion-induction.md): why each emotion is induced the way it is, with references
- [docs/task-design.md](docs/task-design.md): websites, task types and measures
- [docs/consent-form.md](docs/consent-form.md) · [docs/debrief.md](docs/debrief.md): printable forms
- [docs/data-dictionary.md](docs/data-dictionary.md): every output file and column
