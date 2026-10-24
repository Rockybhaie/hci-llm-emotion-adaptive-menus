# Researcher protocol

One session takes about **40 minutes** of study time, or about **55 minutes** including setup and debrief. Book 1 hour per participant.

## Participant schedule (counterbalancing)

Participant numbers decide the order automatically (a 2×2 Latin square). Use consecutive IDs within each group, starting at P01.

| ID | Block 1 | Block 2 |
|---|---|---|
| P01, P05 | emotion 1 · task set A | emotion 2 · task set B |
| P02, P06 | emotion 2 · task set A | emotion 1 · task set B |
| P03, P07 | emotion 1 · task set B | emotion 2 · task set A |
| P04, P08 | emotion 2 · task set B | emotion 1 · task set A |

Emotion 1 and 2 are listed in [config/groups.yaml](../config/groups.yaml). For example, G2 emotion 1 is frustration and emotion 2 is boredom. With 6 participants, each emotion comes first 3 times. Never reuse an ID; the platform refuses an ID that already has data.

## Before the participant arrives (10 min)

1. Check the room against the table in [experimental-setup.md](experimental-setup.md). Note the temperature.
2. Run `python run.py check`. Every row must show ✔.
3. Clean the GSR electrodes and moisten the Polar strap.
4. Prepare the paper consent form ([consent-form.md](consent-form.md)) and the session sheet.

## Arrival (10 min)

1. Welcome the participant. Ask them to switch their phone off and put it away.
2. Give them the **paper consent form** and answer any questions. Do not mention the specific emotions. If asked, say "we're interested in how people navigate websites and how the body responds."
3. When they have signed, attach the HR strap (they can do this privately) and the GSR electrodes (non-mouse hand).
4. Seat them 60–65 cm from the screen and adjust the chair so the eye tracker sees both eyes (Eye Tracker Manager's status view helps).

## Run the session (about 40 min)

```powershell
python run.py session --group G1 --participant P03
```

- The browser opens fullscreen. Say: *"Everything is explained on screen. I'll sit over here; let me know if you need anything."*
- Sit out of view and stay quiet. Watch the terminal:
  - **Sensor status red:** for example, the Polar strap lost contact. Fix it at the next questionnaire screen, not during a video or task block.
  - **Yellow warnings:** for example, weak calibration or a video failing. Note them on the session sheet.
- Do not help with the website tasks. If asked, say *"Just do your best, there's no right way to do it."*
- If you must stop, press Ctrl+C. The data so far is kept, and `--resume` continues from the step that was interrupted.

## Afterwards (5–10 min)

1. The on-screen debrief explains the manipulations. Add a **verbal debrief** ([debrief.md](debrief.md)) and check how the participant feels. This matters most after stress, frustration or sadness. End on a neutral or positive note.
2. If they chose **"please delete my data"**, the platform has already deleted it. The terminal says so.
3. Press Enter in the terminal to close the browser.
4. Remove the sensors, give compensation, and thank the participant.
5. Fill in the session sheet: date, ID, temperature, anything unusual.

## End of each day

```powershell
python run.py export
```

This rebuilds `data/exports/` (sessions, tasks, questionnaires and the combined 10 Hz dataset). Copy `data/` to the shared drive.

## Dry runs

```powershell
python run.py session --group G3 --participant P99 --mock --fast --pilot --windowed
python run.py clean-pilot
```

`--mock` simulates all sensors. `--fast` shortens every timing about 12×. `--pilot` saves to `data/_pilot/`, so real data is never mixed with test runs.
