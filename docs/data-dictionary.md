# Data dictionary

One folder per participant: `data/<participant>/` (dry runs: `data/_pilot/<participant>/`).
Every `t` column is in **seconds on the master clock**; `session.json → clock.t_zero` is the session start.
Screen coordinates (`x`, `y`, gaze, AOIs) are fractions of the browser window (0–1, top-left origin).

## interactions.csv: one row per query (the main dataset)

| Column | Meaning |
|---|---|
| `participant`, `position`, `query_id`, `query_type`, `attempt` | who, which query (1–5 in order shown), its UI type, restart count |
| `start_look`, `looks_seen`, `final_look`, `n_looks` | starting look; sequence of looks on screen (`text>visual>text`); last look; distinct looks |
| `n_auto`, `n_manual`, `n_kept`, `n_back` | automatic switches, "Show this differently" switches, auto switches kept (incl. no answer), "Go back" |
| `t_answer`, `t_done`, `reading_s` | answer first shown, "I'm done" pressed, reading time |
| `time_per_look` | seconds per look, e.g. `text:12.4;visual:40.2` |
| `satisfaction` | 1–7 |
| `preferred_look` | the look the participant said helped most (only asked if more than one was seen; otherwise the one look) |
| `quiz_answer`, `quiz_correct` | the chosen option, 1/0 |
| `emotion_samples`, `face_fraction`, `valence`, `arousal`, `dominant_emotion`, `negative_fraction` | facial emotion summarised over the whole reading time |
| `valence_per_look`, `dominant_per_look` | the same per look, e.g. `text:-0.31;visual:0.05` |

## adaptations.csv: one row per look change (state → action → outcome)

| Column | Meaning |
|---|---|
| `adaptation_id`, `t`, `trigger` | `auto` (the switch rule fired) or `manual` (Show this differently) |
| `from_look`, `to_look`, `n_auto_before` | the change |
| `response`, `response_t`, `response_s` | auto: `keep`, `back` or `none` (prompt timed out = kept); manual: `chosen` |
| `time_on_new_look_s` | how long the new look stayed on screen |
| `final_look`, `satisfaction`, `preferred_look`, `quiz_correct` | the query's outcome |
| `before_samples`, `before_face_fraction`, `before_negative_fraction`, `before_valence`, `before_arousal`, `before_dominant`, `before_p_<class>` | emotion in the window just before the change (the last 4 s) |

## Streams

| File | Columns |
|---|---|
| `emotion.csv` | `t, face, face_x0, face_y0, face_x1, face_y1, emotion, confidence, p_anger … p_surprise, valence, arousal` (rows with `face = 0` have no face) |
| `gaze.csv` | `t, x, y, valid, blink, face, x_raw, y_raw` (webcam); `--sensors mock` writes the two-eye format `left_x … right_pupil_valid` |
| `looks.csv` | `t, query_id, look, reason (initial/auto/manual/back), adaptation_id` |
| `events.csv` | `t, step, query_id, look, source, event, item, x, y, detail` |
| `mouse.csv` | `t, x, y` (up to 60 Hz) |
| `aoi.csv` | `t, snapshot, kind, id, x0, y0, x1, y1`: kind `block` = every answer block and button on screen (`block:<look>:<n>:<type>`, `ui:show-differently`, …), re-logged on render, scroll and resize |
| `markers.csv` | `t, step, step_type, phase, query_id, event (start/end/resumed/abort)` |
| `questionnaires.csv` | `t, tag, query_id, instrument, item, value`: consent, demographics (age, programme, study_confidence), per-query ratings and quiz, final favourite look and comment, debrief choice |

Main `events`: `ask`, `answer_shown`, `look_auto`, `look_manual`, `look_back`, `prompt_shown`, `prompt_keep`, `prompt_back`,
`prompt_none`, `picker_open`, `picker_close`, `done`, `rating_click`, `scroll`, `click`, `key`, `tip_shown`, `pilot_frown`.

## merged.csv: 10 Hz timeline

`t, t_rel, step, phase, query_id, look, face, emotion, p_<class>…, valence, arousal, gaze_x, gaze_y, gaze_valid, gaze_block,
mouse_x, mouse_y, mouse_dist, clicks, scrolls, look_changes`. `gaze_block` is the answer block (from `aoi.csv`) under the gaze
point.

## session.json

Plan (query order, starting looks), status, clock, sensor info, the switch rule used, **content versions** (a hash and the
provenance of each query file), client screen size, calibration result, progress.

`python run.py export` → `data/exports/interactions_all.csv`, `adaptations_all.csv`, `dataset_all.csv` (all `merged`),
`questionnaires_all.csv`, `sessions.csv`.
