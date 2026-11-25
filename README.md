# Emotion-Adaptive Generative UI: Study App

The data-collection app for **runtime emotion-adaptive Generative UI**. A student asks a study assistant in a university
learning portal five questions. Each answer is shown in one of six "looks" (paragraphs, visual, step by step, worked example,
summary, simple). While the student reads, a webcam model estimates their facial emotion; when they look confused or unhappy
for a few seconds, **the answer switches to another look by itself** and asks *"Keep this view or go back?"*. The student can
also press **Show this differently** at any time. After each answer they rate it and answer one quiz question.

Everything is saved on one clock as model-ready data: **which look, under which emotion, helped or not**. That dataset (first
9 participants × 5 queries = 45 interactions, later ~125 students) is what the Generative-UI agent will be trained on.

| | |
|---|---|
| Website | Northfield University student portal (5 courses) with a built-in AI study assistant |
| Queries | 5 from 5 subjects, one per question type: comparison · concept · cause and effect · plan · calculation ([docs/queries.md](docs/queries.md)) |
| Looks | 6 per answer, AI-generated once and frozen ([content/queries/](content/queries/)) |
| Sensors | laptop webcam only: facial emotion (our YOLO11n model) + gaze (EyeTrax) |
| Session | about 13–15 minutes per participant |

---

## Setup (once)

```powershell
pip install -r requirements.txt
pip install --no-deps eyetrax          # webcam gaze (installed without its numpy<2 pin)
python run.py check                    # must end with "Ready."
python run.py camera                   # optional: live window showing what the emotion model sees (q quits)
```

## Commands

| Command | What it does |
|---|---|
| `python run.py check` | Packages, config, every answer, models, port, browser and the webcam sensors |
| `python run.py preview` | Review page: every query in every look, plus the quiz answers (nothing recorded) |
| `python run.py session --participant P01` | Run one participant (fullscreen kiosk browser, webcam on) |
| `… --sensors mock` / `--sensors off` | Simulated emotion and gaze / no webcam at all (answers then only change on request) |
| `… --fast --pilot --windowed` | Dry run: timings ÷ 6, saved in `data/_pilot/`, **Ctrl+Shift+F** in the browser simulates a frown |
| `… --resume` | Continue an interrupted session (a query that was interrupted starts again; rows keep `attempt`) |
| `python run.py camera` | Live webcam window with the emotion model (nothing recorded) |
| `python run.py export` | Combine all participants into `data/exports/` |
| `python run.py clean-pilot` | Delete `data/_pilot/` |
| `python -m pytest` | Automated tests, including a simulated participant over the real API |

Stop a session with **Ctrl+C** in the terminal or **Ctrl+Shift+Q** in the browser; what was recorded so far is kept.
While a session runs, `http://127.0.0.1:8765/monitor` shows the researcher the annotated webcam feed (never the participant).

## A session, screen by screen (~14 min)

```
welcome + consent → 3 questions (age, programme, ML knowledge) → webcam gaze calibration (follow the dot, ~30 s)
→ 30 s calm baseline → 5 queries (≈2 min each) → "which look helped most?" → debrief (keep or delete my data) → thank you
```

Each query: the question is pre-filled in the assistant box → **Ask** → "Generating answer…" → the answer in its starting look →
read (it may switch look; **I'm done** unlocks after 25 s) → satisfaction 1–7 · which version helped most (if it changed) ·
one quiz question.

- **Query order** follows a 5 × 5 Latin square and the **starting look** is rotated, both from the participant number,
  so across 6 participants every query starts once in every look.
- **Switch rule** ([config/genui.yaml](config/genui.yaml) → `adaptation`): at least 75 % of the last 4 s of emotion samples are
  negative (valence below −0.15, or anger + contempt + disgust + fear + sad above 0.5), at most 2 automatic switches per query,
  15 s apart, to a random look not yet seen (unbiased data for the agent).

## Output per participant: `data/<participant>/`

| File | Contents |
|---|---|
| **`interactions.csv`** | **one row per query** (the 45-row dataset): looks seen, time per look, switches, Keep/Back, satisfaction, preferred look, quiz correct, emotion summary per look |
| **`adaptations.csv`** | **one row per look change**: emotion snapshot just before, from → to, auto or manual, Keep / Back / no answer, and the query's outcome |
| `emotion.csv` | facial emotion at ~10 Hz: 8 class probabilities, valence, arousal, face box |
| `gaze.csv` | webcam gaze (screen fractions) |
| `looks.csv` | every look put on screen, with the reason |
| `events.csv`, `mouse.csv`, `aoi.csv` | clicks, scrolls, prompts, picker; mouse at up to 60 Hz; on-screen rectangle of every answer block |
| `markers.csv`, `questionnaires.csv`, `session.json` | step timings, all answers, plan / content versions / sensor info |
| `merged.csv` | **10 Hz timeline**: step, query, look, emotion, gaze and the answer block being looked at, mouse, events |

Every column: [docs/data-dictionary.md](docs/data-dictionary.md). `python run.py export` stacks all participants into
`data/exports/` (`interactions_all`, `adaptations_all`, `dataset_all`, `questionnaires_all`, `sessions`).

## Project layout

```
run.py              the single entry point
config/             genui.yaml (study, looks, switch rule, timings) · devices.yaml (webcam sensors)
content/queries/    the 5 answers × 6 looks (block format) + quiz questions
hci/                Python: session, adaptation rule, content, server, sensors (hci/sensors/webcam.py), export
web/shell/          participant screens (consent, calibration, query, ratings, debrief)
web/portal/         the learning-portal page · web/genui/ the block renderer · web/review/ the content review page
models/             the emotion model (ONNX) and the MediaPipe face model
docs/               queries, protocol, setup, data dictionary, consent, debrief
tests/              automated tests
data/               created by the first session; results only (never committed)
```

## Before the first real participant

1. Team review of the answers: `python run.py preview`, then set `status: reviewed` in each `content/queries/*.yaml`.
2. Fill in the bracketed details in [docs/consent-form.md](docs/consent-form.md).
3. One full pilot on yourself with the real webcam: `python run.py session --participant P99 --pilot --windowed`.

## Credits

The webcam emotion model, gaze adapter and live monitor (`hci/sensors/webcam.py`, `hci/sensing.py`, `hci/monitor.py`, `models/`)
come from Talha's work on the project. The answers in `content/queries/` were generated with Claude and reviewed by the team.
