# Data dictionary

Each session is saved in `data/<group>/<participant>/`. Dry runs (`--pilot`) are saved in `data/_pilot/` instead.
There are **no sensor files**: sensors are handled outside this app (see the [README](../README.md#sensors)).

**Time.** Every `t` column is in **seconds on the shared master clock**. `session.json → clock.t_zero` is the session start; subtract it to get time since start. `merged.csv` already includes this as `t_rel`.

**Screen coordinates** (`x`, `y`, AOIs) are fractions of the browser window, from 0 to 1 with (0, 0) at the top-left. In the fullscreen kiosk this is the whole screen. Pixel sizes (for example `mouse_path_px`) use the window size recorded in `session.json → client`.

## The label columns

These six columns appear, with the same meaning, in `markers`, `events`, `tasks`, `questionnaires` and `merged` (and `phase`, `sub_block`, `menu_id` in `aoi`):

| Column | Meaning |
|---|---|
| `phase` | `welcome`, `consent`, `demographics`, `baseline`, `rating`, `practice`, `induction`, `booster`, `tasks`, `menu_rank`, `washout`, `debrief`, `end`. **Exclude `practice`** from analyses of the experiment; it is a neutral warm-up with each menu. |
| `emotion_block` | 1 or 2 (empty outside the emotion blocks, and in practice) |
| `emotion` | Target emotion of the block; `neutral` for baseline, practice, washout and their ratings; empty for welcome, consent, demographics, debrief |
| `sub_block` | 1, 2 or 3 within an emotion block (empty otherwise) |
| `menu_id` | `M1`–`M9` while a menu is in use: in practice and the sub-block's tasks, and in the sub-block's rating |
| `menu_type` | `hover-dropdown`, `sidebar-tree`, `hub-spoke`, `click-dropdown`, `mega-menu`, `search-first`, `drawer`, `radial`, `two-row-tabs` |

## session.json, plan.json, plan.txt

| Key | Meaning |
|---|---|
| `group`, `participant`, `site`, `emotions`, `menus` | Who and what |
| `plan` | Counterbalancing: `scheme` (1–6), `emotion_order`, `menu_order`, `practice[]`, and `blocks[]` each with `sub_blocks[]` = `{sub_block, menu, subset}`. `plan.json` is the same; `plan.txt` is the printed form |
| `status` | `running`, `complete`, `aborted`, `declined` or `withdrawn` (in the last two cases the folder is deleted) |
| `client` | Browser window and screen size, pixel ratio, whether fullscreen |
| `inductions` | Per induction and booster: MIST trials and accuracy, copying lines, video watch time, … |
| `progress` | `completed_steps`, `started_steps` and `attempts` (how often each step was started), used by `--resume` |

## markers.csv: the labels

`t`, `step`, `step_type`, the six label columns, `event`. `event` is `start`, `end`, `resumed` or `abort: <reason>`.

## events.csv

`t`, `step`, the six label columns, `task_id`, `source`, `event`, `section`, `page`, `item`, `x`, `y`, `detail`.

| Column | Meaning |
|---|---|
| `task_id` | The task in progress, if any (`S3-2`, or `S3-2R` in the boredom block, `P4` in practice) |
| `source` | `shell` (participant screens) or `site` (the website and its menu) |
| `item` | The menu item involved: `nav:<section>`, `nav:home`, `nav:menu`, `nav:search`, `nav:browse`, `item:<section>/<page>` |
| `detail` | Extra information as JSON |

| `event` | Meaning |
|---|---|
| `menu_open` / `menu_close` | The menu left / returned to its resting state. `detail.state` (`open:<section or panel>` / `closed`), `detail.trigger` (hover, click, type, …), `detail.reason` (select, escape, outside, leave, toggle, close, reset, glitch, switch) |
| `item_hover_enter` / `item_hover_exit` | Pointer entered / left a menu item (`detail.dwell_ms` on exit) |
| `item_select` | A menu item was chosen (`detail.level`: section, page, home, control; `detail.via`: click, enter) |
| `search_query` | **M6 only**: `detail.query`, `detail.n_results` |
| `page_view` / `home_view` | Page shown (after any lag); `detail.via` |
| `backtrack` | A navigation to a location already visited in this task (home counts as visited) |
| `click`, `scroll`, `key` | Raw input (key events record the key type only, never text). Site clicks have `detail.target` = the item id or the tag name |
| `sabotage_lag`, `sabotage_click_dropped`, `sabotage_menu_glitch`, `sabotage_answer_expired` | Frustration manipulations |
| `click_while_loading` | Click during a delayed page load |
| `task_start` / `task_end`, `answer_open` / `answer_close` | Task flow |
| `reward` | Joy-block bonus shown |
| `mist_trial`, `mist_warning` | Stress induction and booster trials and the "below average" warnings |
| `copy_line` | Boredom copying task |
| `booster_start` / `booster_end` | A booster ran (`detail.kind`) |
| `video_end` | Film, booster or washout clip finished (`detail.watched_s`; `placeholder: true` if the file was missing) |
| `rating_click` | Each questionnaire click, including changed answers |
| `clock_sync`, `step` | Housekeeping |

## mouse.csv and aoi.csv

- `mouse.csv`: `t`, `x`, `y`, sampled at up to 60 Hz.
- `aoi.csv`: `t`, `snapshot`, `kind`, `id`, `x0`, `y0`, `x1`, `y1`, `phase`, `sub_block`, `menu_id`. A snapshot of on-screen rectangles is taken whenever the layout changes (a menu opens or closes, an animation settles, the window resizes). A snapshot lists **every menu item currently on screen**, so hidden items have no rectangle.
  - `kind = menu`: menu items (`nav:<section>`, `nav:home`, `nav:menu`, … and `item:<section>/<page>`)
  - `kind = content`: items on the page (`content:<item-id>`)
  - `kind = taskbar`: task text, Answer button, answer options

  A snapshot with an empty `id` clears that kind.

## tasks.csv

One row per task, including practice (`phase = practice`). The six label columns, then:

| Column | Meaning |
|---|---|
| `subset` | `S1`–`S6` (or `P`, the practice pool) |
| `attempt` | 1, or 2, 3, … if the sub-block was repeated after `--resume` |
| `variant` | `repetitive` in the boredom block |
| `task_id`, `type` | e.g. `S3-2`, `lookup` / `extreme` / `compare` |
| `target_pages` | Pages the task needs, separated by `;` |
| `t_start`, `t_end`, `duration_s` | Timing |
| `outcome` | `correct`, `incorrect`, `timeout`, `not_reached`, `abandoned`, `aborted` |
| `correct` | 1 if `outcome` is `correct`, else 0 |
| `answer`, `correct_answer` | |
| `shortest_clicks`, `shortest_steps` | Fewest clicks / discrete steps this menu needs for the target page(s) from home ([MENUS.md](../MENUS.md#definitions-used-throughout)) |
| `mouse_path_px` | Mouse path length during the task, in pixels |
| `clicks`, `menu_clicks` | Clicks inside the site; of which on menu items |
| `menu_opens`, `page_views`, `wrong_pages`, `backtracks` | Counts of `menu_open`, `page_view`, pages that are not a target, and `backtrack` events |
| `sabotage_events`, `answer_attempts` | Induced faults that hit the task; submissions including "session expired" ones |

See [task-design.md](task-design.md).

## subblocks.csv

One row per sub-block (six per participant), practice excluded. For a sub-block repeated after an interruption only the **last attempt** is used.

| Columns | Meaning |
|---|---|
| `emotion_block`, `emotion`, `sub_block`, `menu_id`, `menu_type`, `subset`, `attempt` | Which cell |
| `tasks_total`, `correct`, `accuracy`, `timeouts`, `not_reached` | Performance |
| `duration_sum_s`, `duration_mean_s`, `duration_median_s`, `duration_mean_correct_s` | Time |
| `clicks`, `menu_clicks`, `menu_opens`, `page_views`, `wrong_pages`, `backtracks`, `sabotage_events`, `answer_attempts`, `mouse_path_px` | Sums of the task columns |
| `shortest_clicks`, `shortest_steps`, `excess_menu_clicks` | Sums of the minimum costs; `excess_menu_clicks = menu_clicks − shortest_clicks` |
| `mood_stressed`, `mood_calm`, `mood_frustrated`, `mood_bored`, `mood_happy`, `mood_sad` | The six mood ratings (1–7) asked straight after this sub-block |
| `tlx_mental`, `tlx_effort`, `tlx_frustration` | The three workload ratings (0–100) straight after this sub-block |
| `menu_rank` | Preference rank (1 = best of the three) given at the end of the emotion block |

## questionnaires.csv

Long format: `t`, `tag`, the six label columns, `instrument`, `item`, `value`.

| `instrument` | Items | Scale |
|---|---|---|
| `consent` | `agreed` | 0/1 |
| `demographics` | `age`, `gender`, `handedness`, `vision`, `computer_hours`, `site_familiarity`, `caffeine_2h` | text |
| `sam` | `valence`, `arousal`, `dominance` | 1–9 |
| `emotions` | `stressed`, `calm`, `frustrated`, `bored`, `happy`, `sad` | 1–7 |
| `tlx_short` | `mental`, `effort`, `frustration` | 0–100 in steps of 5 |
| `menu_rank` | the menu id (`M1` …) | 1–3, 1 = most preferred |
| `debrief` | `retain_data` | yes / withdraw |

`tag` values: `consent`, `demographics`, `baseline`, `post_induction_1`, `subblock_1_1` … `subblock_1_3`, `menu_rank_1`, `post_washout`, `post_induction_2`, `subblock_2_1` … `subblock_2_3`, `menu_rank_2`, `debrief`. The sub-block ratings (`emotions` + `tlx_short`) always ask all six emotion items, in an order shuffled per participant, so the target emotion is never revealed.

## merged.csv: the model-ready behavioural timeline, 10 Hz

| Column | Meaning |
|---|---|
| `t`, `t_rel` | Bin start (master clock / seconds since session start) |
| `step`, the six label columns | Labels from markers.csv (`phase = setup` = before the first screen) |
| `task_id` | Task in progress, if any |
| `menu_state` | While a site is on screen: `closed` or `open:<section or panel>`, from `menu_open` / `menu_close`; empty otherwise |
| `mouse_x`, `mouse_y`, `mouse_dist` | Last mouse position and distance moved in the bin |
| `clicks`, `menu_events`, `page_views`, `backtracks`, `sabotage` | Event counts in the bin (`clicks` = clicks inside the site; `menu_events` = `menu_open` + `menu_close` + `item_select`) |

`python run.py export` stacks all completed sessions into `data/exports/`: `dataset_all.csv` (merged), `tasks_all.csv`, `subblocks_all.csv`, `events_all.csv`, `questionnaires_all.csv` (each with `group` and `participant` columns first) and `sessions.csv` (one row per session: plan, status, duration).
