# Data dictionary

Each session is saved in `data/<group>/<participant>/`. Dry runs (`--pilot`) are saved in `data/_pilot/` instead.

**Time.** Every `t` column is in **seconds on the shared master clock**. `session.json → clock.t_zero` is the session start; subtract it to get time since start. `merged.csv` already includes this as `t_rel`.

**Screen coordinates** (`x`, `y`, gaze, AOIs) are fractions of the screen, from 0 to 1 with (0, 0) at the top-left. This is the same system Tobii uses for its display area, so gaze can be compared with on-screen positions directly.

## session.json

| Key | Meaning |
|---|---|
| `group`, `participant`, `site`, `emotions` | Who and what |
| `plan.scheme`, `blocks[]` | Counterbalancing: the emotion and task set (A/B) of block 1 and block 2 |
| `status` | `running`, `complete`, `aborted`, `declined` or `withdrawn` (in the last two cases the folder is deleted) |
| `devices` | The adapter, device info and sample count for each sensor |
| `client` | Screen and browser size, pixel ratio, whether fullscreen |
| `calibration` | Eye-tracker calibration status, mean validation error and attempts |
| `inductions` | Per block: MIST trials and accuracy, copying lines, video watch time, … |
| `progress` | Completed steps, which `--resume` uses |

## markers.csv: the labels

| Column | Meaning |
|---|---|
| `t` | Time of the event |
| `step`, `step_type` | Index and type of the step (welcome, consent, …, tasks, rating, end) |
| `phase` | `welcome`, `consent`, `demographics`, `calibration`, `baseline`, `rating`, `induction`, `tasks`, `washout`, `debrief`, `end` |
| `block` | 1 or 2, empty outside the emotion blocks |
| `emotion` | Target emotion of the block; `neutral` for baseline, washout and their ratings |
| `event` | `start`, `end`, `resumed` or `abort: <reason>` |

## Sensor files

| File | Columns |
|---|---|
| `gaze.csv` | `t`, `device_ts`, `left_x`, `left_y`, `left_valid`, `right_x`, `right_y`, `right_valid`, `left_pupil`, `left_pupil_valid`, `right_pupil`, `right_pupil_valid` (pupil in mm) |
| `gsr.csv` | `t`, `gsr_us` (µS), plus raw or extra channels depending on the adapter |
| `hr.csv` | `t`, `hr_bpm`, `rr_ms` (RR intervals separated by `;`, Polar only) |
| `clock_sync.csv` | `t`, `stream`, `adapter`, `offset_s`: Tobii clock offsets (real hardware only) |

## events.csv

| Column | Meaning |
|---|---|
| `t`, `step`, `block`, `task_id` | When, and the current task if any |
| `source` | `shell` (participant screens) or `site` (the website) |
| `event` | See the table below |
| `section`, `page`, `item` | The menu section, page or item involved |
| `x`, `y` | Click position (screen fraction) |
| `detail` | Extra information as JSON |

| `event` | Meaning |
|---|---|
| `menu_open` / `menu_switch` / `menu_close` | Drop-down opened (`detail.trigger`: hover or click), moved to another section, or closed (`detail.reason`: leave, select, escape, outside, glitch, reset) |
| `menu_hover` | Pointer entered a drop-down item |
| `menu_select` | Item chosen in the menu |
| `page_view` / `home_view` | Page shown (after any lag) |
| `click`, `scroll`, `key` | Raw input (key events record the key type only, never text) |
| `sabotage_lag`, `sabotage_click_dropped`, `sabotage_menu_glitch`, `sabotage_answer_expired` | Frustration manipulations |
| `click_while_loading` | Click during a delayed page load |
| `task_start` / `task_end`, `answer_open` / `answer_close` | Task flow |
| `reward` | Joy-block bonus shown |
| `mist_trial`, `mist_warning` | Stress induction trials and the "below average" warnings |
| `copy_line` | Boredom copying task |
| `video_end` | Film or washout clip finished (`detail.watched_s`) |
| `rating_click` | Each questionnaire click, including changed answers |
| `calibration_attempt`, `clock_sync`, `step` | Housekeeping |

## mouse.csv and aoi.csv

- `mouse.csv`: `t`, `x`, `y`, sampled at up to 60 Hz.
- `aoi.csv`: `t`, `snapshot`, `kind`, `id`, `x0`, `y0`, `x1`, `y1`. A snapshot of on-screen rectangles is taken whenever the layout changes.
  - `kind = menu`: menu bar buttons (`nav:<section>`) and open drop-down items (`item:<section>/<page>`)
  - `kind = content`: items on the page (`content:<item-id>`)
  - `kind = taskbar`: task text, Answer button, answer options

  A snapshot with an empty `id` clears that kind.

## tasks.csv

One row per task: `block`, `emotion`, `task_set`, `variant` (`repetitive` in boredom blocks), `task_id`, `type`, `target_pages`, `t_start`, `t_end`, `duration_s`, `outcome`, `answer`, `correct_answer`, `clicks`, `menu_opens`, `page_views`, `wrong_pages`, `sabotage_events`, `answer_attempts`. See [task-design.md](task-design.md).

## questionnaires.csv

Long format: `t`, `tag`, `block`, `emotion`, `instrument`, `item`, `value`.

| `instrument` | Items | Scale |
|---|---|---|
| `consent` | `agreed` | 0/1 |
| `demographics` | `age`, `gender`, `handedness`, `vision`, `computer_hours`, `site_familiarity`, `caffeine_2h` | text |
| `sam` | `valence`, `arousal`, `dominance` | 1–9 |
| `emotions` | `stressed`, `calm`, `frustrated`, `bored`, `happy`, `sad` | 1–7 |
| `tlx` | `mental`, `physical`, `temporal`, `performance` (0 = perfect), `effort`, `frustration` | 0–100 in steps of 5 |
| `debrief` | `retain_data` | yes / withdraw |

`tag` values: `baseline`, `post_induction_1`, `post_tasks_1`, `post_washout`, `post_induction_2`, `post_tasks_2`.

## merged.csv: model-ready, 10 Hz

| Column | Meaning |
|---|---|
| `t`, `t_rel` | Bin start (master clock / seconds since session start) |
| `step`, `phase`, `block`, `emotion` | Labels from markers.csv (`setup` = before the first screen) |
| `task_id` | Task in progress, if any |
| `gaze_x`, `gaze_y`, `gaze_valid` | Mean gaze over valid eyes; fraction of valid samples |
| `pupil_mm` | Mean pupil diameter |
| `gaze_aoi` | What the participant was looking at: `menu:item:<section>/<page>`, `menu:nav:<section>`, `content:<item>`, `taskbar:<id>` |
| `gsr_us` | Mean skin conductance (forward-filled) |
| `hr_bpm` | Latest heart rate (forward-filled) |
| `mouse_x`, `mouse_y`, `mouse_dist` | Last mouse position and distance moved in the bin |
| `clicks`, `menu_events`, `page_views`, `sabotage` | Event counts in the bin |

`python run.py export` stacks all completed sessions into `data/exports/dataset_all.csv`, `tasks_all.csv` and `questionnaires_all.csv` (each with `group` and `participant` columns), plus `sessions.csv` (one row per session).
