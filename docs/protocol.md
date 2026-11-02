# Researcher protocol

One session takes about **50 minutes** of study time (see [How long it takes](#how-long-it-takes)), or about 70 minutes including arrival and debrief. Book 1 hour 15 minutes per participant.

## Participant schedule (counterbalancing)

Participant numbers decide everything automatically. Use consecutive IDs within each group, starting at P01, and **recruit in complete sets of six** (P01–P06) so every combination occurs once. Never reuse an ID; the platform refuses an ID that already has data.

`k = (number − 1) mod 6`. Emotion 1 and 2 are listed in [config/groups.yaml](../config/groups.yaml) (for G2: frustration, boredom); menus A, B, C are the group's three menus in the order listed there (for G2: M4, M5, M6).

| ID | Emotion order | Menu order (both emotion blocks) |
|---|---|---|
| P01, P07 | 1 → 2 | A → B → C |
| P02, P08 | 2 → 1 | B → C → A |
| P03, P09 | 1 → 2 | C → A → B |
| P04, P10 | 2 → 1 | A → B → C |
| P05, P11 | 1 → 2 | B → C → A |
| P06, P12 | 2 → 1 | C → A → B |

The exact plan (emotion order, menu order, which subset in which cell) is printed at the start of every session and saved in the participant's folder (`plan.txt`). Across a complete set of six: each emotion comes first three times, each menu is first, second and third twice, every emotion × menu cell is paired with each of the six task subsets once. [README](../README.md#counterbalancing) has the rule. With 15–18 participants you get 5–6 per group: run P01–P06 in each group, drop any extras from the analysis rather than from the plan.

## Before the participant arrives (10 min)

1. Check the room against [experimental-setup.md](experimental-setup.md) (lighting, temperature, quiet). Note the temperature.
2. Run `python run.py check`. Every row must show ✔, except the two optional booster clips (a warning is expected until you supply them).
3. Run `python run.py preview --group <G> --menu <M>` for the group's three menus if anything has been changed.
4. Prepare the paper consent form ([consent-form.md](consent-form.md)) and the session sheet.
5. If sensors run beside this app, start and check them. They are not controlled from here.

## Arrival (10 min)

1. Welcome the participant. Ask them to switch their phone off and put it away.
2. Give them the **paper consent form** and answer any questions. Do not mention the specific emotions or that the *menu* is the thing being compared. If asked, say "we're interested in how people navigate websites and how they feel while they do it."
3. When they have signed, attach any sensors (see your sensor protocol).
4. Seat them 60–65 cm from the screen.

## Run the session (about 50 min)

```powershell
python run.py session --group G1 --participant P03
```

- The terminal prints the plan. The browser opens fullscreen. Say: *"Everything is explained on screen. I'll sit over here; let me know if you need anything."*
- Sit out of view and stay quiet. Watch the terminal: the current step, emotion, sub-block and menu are shown. **Yellow warnings** (for example "Browser is not fullscreen" or a missing clip) go on the session sheet.
- **Practice** (about 4 min) introduces each of the three menus. You may answer questions about *how a menu works* here, not afterwards. Do not help with the website tasks themselves. If asked, say *"Just do your best, there's no right way to do it."*
- The menu changes at the start of each sub-block, announced on screen. This is expected, not a fault.
- If you must stop, press Ctrl+C. The data so far is kept, and `--resume` continues from the step that was interrupted (a sub-block interrupted part-way is repeated from its first task).

## Afterwards (5–10 min)

1. The on-screen debrief explains the manipulations, including that the menus varied on purpose. Add a **verbal debrief** ([debrief.md](debrief.md)) and check how the participant feels. This matters most after stress, frustration or sadness. End on a neutral or positive note.
2. If they chose **"please delete my data"**, the platform has already deleted it. The terminal says so.
3. Press Enter in the terminal to close the browser.
4. Remove any sensors, give compensation, and thank the participant.
5. Fill in the session sheet: date, ID, temperature, anything unusual.

## End of each day

```powershell
python run.py export
```

This rebuilds `data/exports/` (`dataset_all`, `tasks_all`, `subblocks_all`, `events_all`, `questionnaires_all`, `sessions`). Copy `data/` to the shared drive.

## Dry runs

```powershell
python run.py session --group G3 --participant P99 --fast --pilot --windowed
python tools/participant_bot.py --group G3 --participant P01              # a scripted participant, whole session, fast
python tools/participant_bot.py --group G3 --participant P01 --real-time  # same at real timings (about 50 min)
python run.py clean-pilot
```

`--fast` shortens every timing about 12×. `--pilot` saves to `data/_pilot/` so real data is never mixed with test runs, and missing videos become marked placeholders. The scripted participant answers every screen through the menus' own rules, retries when an induced fault swallows a click, and answers about 15 % of tasks wrongly.

## How long it takes

`python run.py check` prints a planned length per group from the configured timings and assumed reading speeds (consent and
demographics 4 min, 20–25 s per rating page, 26 s per task, …), both typical and worst-case (every task runs to its time limit):

| Group | Planned, typical | Planned, worst case |
|---|---|---|
| G1 | about 45 min | about 48 min |
| G2 | about 42 min | about 47 min |
| G3 | about 49 min | about 54 min (the two film clips are long) |

**Measured in real-time dry runs** (the scripted participant in `tools/participant_bot.py --real-time`, full configured timings, a real Edge window):

| Run | Session clock | Timed parts measured |
|---|---|---|
| G1 / P01 | 27.1 min | rest 181 s, inductions 189 s and 180 s, washout 151 s, boosters 38–42 s each |
| G3 / P02 | 28.0 min | rest 182 s, inductions 211 s and 181 s (placeholders), washout 151 s, boosters 37–47 s each |

These totals are **not** the length of a real session. The timed parts above are genuine (about 14 min of the session), but the
scripted participant answers a task in about 15 s, a whole sub-block in about 63 s and a practice menu in about 30 s, much
faster than a person (the planning table assumes 26 s per task and 75 s per practice menu), and it does not read. The
human-paced parts are therefore *modelled*, not measured, and the planned 42–49 min typical / 47–54 min worst case in the
table is the figure to use. **No group goes above 55 min in that model, but G3 comes close**: its two real film clips (5 min 46 s
and 3 min 53 s plus 30 s of reflection) are longer than the 3 min placeholders the dry run used. Time one real participant in the pilot and
adjust `timings` in `config/experiment.yaml` if it runs long (the easiest cuts are `baseline_rest` and `washout`).
