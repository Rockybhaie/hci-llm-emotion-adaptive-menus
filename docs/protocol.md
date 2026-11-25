# Researcher protocol

A session takes about **14 minutes** of study time, or about **20 minutes** including setup and the short chat afterwards.
The first run is 9 participants (P01–P09), so about 3 hours on one laptop.

## Participant numbers

Use consecutive IDs: P01, P02, … Never reuse an ID; the app refuses an ID that already has data. The number decides the order
of the five queries (5 × 5 Latin square) and which look each query starts in (rotated over 6 participants), so consecutive
numbers keep the design balanced. The plan is printed in the terminal when the session starts.

## Before the participant arrives (5 min)

1. Room: normal, even lighting on the face (no window behind the participant), quiet, phone notifications off.
2. `python run.py check`: every row must be ✔ (the content rows show ! until the team has reviewed the answers).
3. Close Teams, Zoom or anything else that might use the webcam.

## Arrival (3 min)

1. Seat the participant about an arm's length from the laptop, face centred in the webcam, light on their face.
2. Optional: sign the paper consent form ([consent-form.md](consent-form.md)). The on-screen consent is the minimum.
3. Do not explain that answers change with their expression; say: *"You'll use a study assistant in a university portal.
   Everything is explained on screen."*

## Run the session (~14 min)

```powershell
python run.py session --participant P03
```

- The browser opens fullscreen. Sit out of the participant's view and stay quiet.
- Watch the terminal: current query and look, the live facial emotion, sensor rates and warnings.
  `http://127.0.0.1:8765/monitor` (on your own screen only) shows the annotated webcam feed.
- If "no face" persists, ask the participant (between queries) to move back into view.
- Do not help with the questions. If asked: *"Just answer as best you can."*
- To stop: **Ctrl+C** (data kept); continue later with `--resume`.

## Afterwards (3 min)

1. The on-screen debrief explains the adaptation and asks whether we may keep the data; a "delete" choice deletes the folder
   automatically. Add the verbal debrief ([debrief.md](debrief.md)).
2. Press **Enter** in the terminal to close the browser.
3. Note anything unusual (lighting, glasses, interruptions) on the session sheet.

## End of the day

```powershell
python run.py export
```

builds `data/exports/` (`interactions_all.csv` is the 45-row dataset after 9 participants). Copy `data/` to the shared drive.

## Dry runs

```powershell
python run.py session --participant P99 --pilot --windowed                  # real webcam, saved in data/_pilot/
python run.py session --participant P98 --sensors mock --fast --pilot --windowed   # no webcam needed, ~4 min
python run.py clean-pilot
```

In `--pilot` sessions **Ctrl+Shift+F** simulates a frown for 6 s (with `--sensors mock`), to see an automatic switch and the
Keep / Go back prompt.
