# Emotion-Adaptive Menus: Experimental App (phase 1, nine menus)

This app runs one complete experimental session with one command. It induces an emotion, has the participant do website
tasks with **three different menus**, and saves what they did, how well they did it and how they felt, all on one clock,
as model-ready data.

It is the data-collection app for an emotion-adaptive navigation system. A later model will learn the link between
behaviour (clicks, delays, mouse movement, backtracking), emotion and menu performance, and a sensor-free product will
then show the menu that worked best for a user's inferred state. **Sensors (GSR, EEG, eye tracking) are not part of this
app**; they are handled elsewhere (see [Sensors](#sensors)).

| Group | Emotions | Website (our own; information architecture modelled on WebArena) | Menus ([MENUS.md](MENUS.md)) |
|---|---|---|---|
| **G1** | Stress vs Calm | Northfield University student portal | M1 hover drop-down · M2 sidebar tree · M3 hub and spoke |
| **G2** | Frustration vs Boredom | Everyday Market online store | M4 click drop-down · M5 mega-menu · M6 search-first |
| **G3** | Joy (amusement) vs Sadness | Threadline discussion forum | M7 hamburger drawer · M8 radial menu · M9 two-row tabs |

Menus are nested within groups. Every participant does **both** emotions of their group and uses **all three** menus of
their group in **each** emotion (six cells: 2 emotions × 3 menus). The order of emotions, the order of menus and which of
six matched task subsets goes with which cell are assigned automatically from the participant number; **P01–P06 of a group
are one complete balanced set**.

---

## Quick start

```powershell
pip install -r requirements.txt                       # once
python run.py check                                   # config, task answers, menus, videos, browser: must say "Ready."
python run.py preview --group G2 --menu M5            # look at any menu without recording (see MENUS.md)
python run.py session --group G2 --participant P04    # run one participant
```

`session` prints the participant's plan (emotion order, menu order, which subset in which cell), opens a fullscreen kiosk
browser, guides the participant through about **50 minutes** and saves everything to `data/G2/P04/`. The terminal shows
the current phase, emotion, sub-block and menu, plus any warnings.

| Command | What it does |
|---|---|
| `python run.py check [--group G1] [--dry-run]` | Packages, config, every task answer in every menu, stimulus videos, port, browser, and the planned session length. `--dry-run` turns missing videos into warnings |
| `python run.py preview --group G2 --menu M5` | Browse a group's website with one of its menus, nothing recorded; the green box lists the events the menu logs |
| `python run.py session --group G1 --participant P01` | Run a real session |
| `… --fast --pilot` | Dry run: every timing ÷ 12, saved in `data/_pilot/`, missing videos shown as placeholders |
| `… --resume` | Continue an interrupted session from the sub-block it was in (see [Resuming](#resuming)) |
| `… --windowed` / `--no-browser` | Normal browser window / don't open a browser |
| `python run.py export` | Combine all sessions into `data/exports/` |
| `python run.py clean-pilot` | Delete `data/_pilot/` |
| `python -m pytest` | All 145 tests (about 13 min; 6 are skipped by default: five of the six whole-session dry runs, which run with `HCI_FULL_DRY_RUN=1`). `-m "not slow"` skips the every-task-in-every-menu test and the dry run (about 5 min) |
| `python tools/participant_bot.py --group G2 --participant P03` | A scripted participant completes a whole session in Edge (a fast dry run; `--real-time` for real timings) |

To stop a session, press **Ctrl+C** in the terminal or **Ctrl+Shift+Q** in the browser. Both save what was recorded so far.

## What a session looks like

```
consent → demographics → 3 min rest (baseline) → mood rating
→ Menu practice (about 4 min): for each of the 3 menus a neutral introduction + 2 practice tasks     [phase = practice]
→ Emotion block 1
     induction (about 3 min) → mood rating
     sub-block 1: menu A  4 tasks → mood rating + 3-item workload
     booster (30–45 s)  → sub-block 2: menu B  4 tasks → mood rating + workload
     booster (30–45 s)  → sub-block 3: menu C  4 tasks → mood rating + workload
     rank the 3 menus you just used (preference)
→ neutral video (2.5 min) → mood rating
→ Emotion block 2: the same, with the group's other emotion and the same menu order
→ debrief (with the option to withdraw) → thank you
```

- The **emotion manipulations during tasks** (countdown and "compared with others" banner, deliberate faults, repetitive
  wording, surprise rewards …) apply to **every sub-block, identically for the three menus**. They are implemented once in the
  site engine, not in the menus; each fault has an equivalent in every menu ([MENUS.md](MENUS.md#induced-faults-menu-independent)).
- **Boosters** re-cue the emotion before sub-blocks 2 and 3 (not before 1: the induction has just run): a 30 s arithmetic round
  (stress), 40 s of paced breathing (calm), a speed-bonus reminder with a fixed unfavourable "current rank" (frustration),
  30 s of dull copying (boredom), a short clip (joy) and a short clip followed by quiet reflection (sadness).
- Each sub-block has exactly **4 tasks** with a per-task time limit (40 s; 30 s with a visible countdown in the stress block).
- **Session length**: `python run.py check` prints the planned length for each group (typical, and worst case if every task
  times out). Real-time scripted dry runs are in the project notes ([docs/protocol.md](docs/protocol.md#how-long-it-takes)).

## Counterbalancing

Deterministic from the participant number `n` within a group, with `k = (n − 1) mod 6`:

- emotion order: `k mod 2` (2 options) · menu order: row `k mod 3` of a cyclic Latin square (3 options). Because 2 and 3 are
  coprime, the six `k` give each of the six emotion-order × menu-order combinations exactly once. Both emotion blocks of
  one participant use the same menu order, and practice follows it.
- task subsets S1–S6: the cell `c = emotion × 3 + menu` gets subset `(c + k) mod 6`. Every participant meets every subset
  exactly once, and across a complete set of six every cell sees every subset once, so each subset is paired with each menu
  twice and each emotion three times. `tests/test_core.py` verifies all of this.

The full plan is printed when the session starts and saved as `plan.json` / `plan.txt` in the participant's folder, e.g.

```
scheme 1 of 6: emotion order stress > calm, menu order M1 > M2 > M3
  block 1 (stress): 1: M1/S1   2: M2/S2   3: M3/S3
  block 2 (calm):   1: M1/S4   2: M2/S5   3: M3/S6
```

## Output per participant: `data/<group>/<participant>/`

Every row of `markers`, `events`, `tasks`, `questionnaires` and `merged` carries the same label columns:
`phase`, `emotion_block`, `emotion`, `sub_block`, `menu_id`, `menu_type`. Practice rows have `phase = practice`.

| File | Contents |
|---|---|
| `session.json`, `plan.json`, `plan.txt` | Group, plan, client screen, progress, status |
| `markers.csv` | Start and end of every step; these are the labels |
| `events.csv` | Every click, menu open/close/hover/select, search query, page view, backtrack, fault, key press |
| `mouse.csv` | Mouse position at up to 60 Hz |
| `aoi.csv` | On-screen rectangles of every menu item, page content and the task bar |
| `tasks.csv` | One row per task: outcome, time, clicks, menu clicks, wrong pages, backtracks, shortest possible clicks and steps for that menu, mouse path length, … |
| `subblocks.csv` | **One row per sub-block:** the task measures aggregated, plus the six mood ratings, the workload ratings and the menu preference |
| `questionnaires.csv` | Consent, demographics, SAM, mood ratings, workload, menu ranking, debrief choice |
| `merged.csv` | **The model-ready timeline:** 10 Hz, with phase, emotion, menu, sub-block, task, mouse position, menu state and event counts |

Every column is described in [docs/data-dictionary.md](docs/data-dictionary.md). `python run.py export` stacks all
sessions into `data/exports/` (`dataset_all`, `tasks_all`, `subblocks_all`, `events_all`, `questionnaires_all`, `sessions`).

## Sensors

Sensors are **out of scope**. The app does not start, connect to, wait for or record any sensor device, there is no sensor
flag or mode, and `run.py check` does not test any. The adapter files in `hci/sensors/`, `config/devices.yaml` and the
eye-tracker calibration screen (`web/shell/js/steps/calibration.js`) are left in the repository untouched and unused,
so nothing is lost; nothing depends on them. The consent text still mentions eye tracking, skin conductance and heart rate,
because the sensors are expected to run beside this app; edit [web/shell/content/consent.html](web/shell/content/consent.html)
and [docs/consent-form.md](docs/consent-form.md) if that is not the case. All events carry timestamps on one master clock
(`session.json → clock`) so sensor data recorded elsewhere can be aligned later; `aoi.csv` already records every menu item's
rectangle (as fractions of the browser window) for mapping gaze to menu items.

## Resuming

`--resume` continues from the **first unfinished step**, which is a whole sub-block's task step (or a practice, booster,
rating …). A sub-block interrupted part-way is restarted from its first task: the first attempt's rows stay in the files with
`attempt = 1` and the repeat has `attempt = 2`. `subblocks.csv` uses only the last attempt. Resuming is refused if
`config/groups.yaml` or the participant plan changed since the session started.

## Before the first real participant

1. **Videos.** See [stimuli/README.md](stimuli/README.md). The two optional booster clips for G3 are not included (a marked
   placeholder screen is shown instead; `check` warns).
2. **Forms.** Fill in the bracketed contact and ethics details in [docs/consent-form.md](docs/consent-form.md).
3. **Look at the nine menus** with `preview` and try the real thing once on yourself: `python run.py session --group G2 --participant P99 --fast --pilot --windowed`.

## Project layout

```
run.py              the single entry point
MENUS.md            specification of the nine menus
config/             groups, emotions, boosters, menus, timings, task subsets   ← edit here
hci/                Python: session flow, counterbalancing, menu click models, server, export
web/shell/          what the participant sees (consent, inductions, boosters, ratings, ranking, task screen)
web/core/           the site engine (rendering, logging, faults) and web/core/menus/ (the nine plug-ins)
web/sites/          the three websites (site.json content + theme.css)
tools/              participant_bot.py: a scripted participant for dry runs
stimuli/            video clips + the neutral-clip generator
docs/               setup, protocol, rationale, task design, data dictionary, consent and debrief
tests/              automated tests
data/               created by the first session; results only
hci/sensors/, config/devices.yaml, web/shell/js/steps/calibration.js   unused (see Sensors)
```

## Documentation

- [MENUS.md](MENUS.md): the nine menus, their rules, costs, events and faults
- [docs/protocol.md](docs/protocol.md): researcher script and participant schedule
- [docs/task-design.md](docs/task-design.md): websites, task subsets, measures
- [docs/emotion-induction.md](docs/emotion-induction.md): why each emotion is induced the way it is (with boosters)
- [docs/data-dictionary.md](docs/data-dictionary.md): every output file and column
- [docs/experimental-setup.md](docs/experimental-setup.md): room and PC settings (sensor sections are for the separate sensor stage)
- [docs/consent-form.md](docs/consent-form.md) · [docs/debrief.md](docs/debrief.md): printable forms
