# Experimental setup

> **Scope.** This app records behaviour only. **Sensors are not part of it**: the app does not start, read or wait for any device. The room and PC settings below apply to every session. The sections on hardware placement, the adapter table and clock synchronisation describe the **separate sensor stage** (the adapter files in `hci/sensors/` are kept unchanged but unused) and are kept for reference. Keep the room identical across participants whatever the sensors are, because lighting and temperature affect eye and skin signals.

Use the same room, PC, screen and settings for every participant in every group. Differences in light, temperature or screen setup show up directly in pupil size and GSR.

## Room

| Item | Setting | Why |
|---|---|---|
| Lighting | Ceiling lights on, blinds closed, no direct light on the screen or face | Pupil size depends on light; a constant level keeps it comparable |
| Temperature | 21–23 °C, logged on the session sheet | Skin conductance rises with warmth and sweating (Boucsein, 2012) |
| Noise | Quiet room, door closed, phones silent | Sudden sounds cause skin conductance responses |
| Researcher | Seated behind and to the side of the participant, out of view, not talking | Being watched is itself a stressor |

## Hardware

| Device | Placement |
|---|---|
| **Monitor** | 24", 1920×1080, Windows display scaling **100%**, brightness fixed (write the value down) |
| **Tobii Pro eye tracker** (Nano / Fusion / Spark) | Magnetically mounted on the bottom edge of the monitor, centred. Set up the display area once in *Tobii Pro Eye Tracker Manager* |
| **Chair** | Fixed, without wheels if possible. Eyes 60–65 cm from the screen, roughly level with its upper third |
| **GSR** | Two electrodes on the middle phalanges of the index and middle fingers of the **non-mouse hand**. Ask the participant to rest that hand still on the desk |
| **Heart rate** | Polar H10: moisten the strap electrodes and fit it just below the chest muscles. A finger PPG (Shimmer) goes on the ring finger of the GSR hand |
| **Headphones or speakers** | Same volume for everyone (write the value down), needed for the film clips |
| **Mouse** | Wired, same model for everyone, on the participant's preferred side |

After attaching the GSR electrodes, wait **at least 5 minutes** before starting. The skin–electrode contact needs time to settle. Consent and calibration fill that time naturally.

## Choosing the GSR and heart-rate adapters

Edit [config/devices.yaml](../config/devices.yaml), install the library, then run `python run.py check`.

| You have | `adapter:` | Install | Notes |
|---|---|---|---|
| Shimmer3 GSR+ | `gsr: shimmer` | `pip install pyshimmer` | Enable GSR + PPG (~128 Hz) in Shimmer Consensys first; set the Bluetooth COM port |
| Polar H10 | `hr: polar_h10` | `pip install bleak` | Pair nothing in Windows; the adapter finds the strap by name |
| Any device that streams over LSL (BITalino, Empatica bridge, OpenSignals, Shimmer LSL apps …) | `lsl` | `pip install pylsl` | Channel 0 must be µS (GSR) or BPM (HR) |
| Arduino / Grove GSR or pulse sensor | `serial` | `pip install pyserial` | The sketch prints one number per line |
| Tobii Pro | `eye_tracker: tobii` (default) | `pip install tobii-research` | Close Eye Tracker Manager before a session |

The Shimmer, Polar, LSL and serial adapters were written against the vendors' published APIs but could not be tested here without the devices. Do one full `--pilot` session with the real hardware before the first participant.

## PC settings

- Windows **Focus assist / Do not disturb** on. Close Teams, OneDrive, Windows Update and anything else that shows pop-ups.
- Mains power, sleep and screensaver off.
- The study opens in **Microsoft Edge kiosk mode** (fullscreen, no browser controls), with a fresh profile for every session. Use the same screen size and **Windows display scaling 100 %** for every participant: menu positions and sizes (and the AOI rectangles in `aoi.csv`) depend on the window size, and the app warns if the browser is not fullscreen.
- One monitor only, or make the study screen the primary display. Gaze coordinates assume the browser fills the eye tracker's screen.

## Timing and synchronisation

All streams share one master clock (LSL `local_clock` when `pylsl` is installed, otherwise the Windows high-resolution counter):

- **Tobii:** the device clock offset is measured at start-up and every 30 s and saved in `clock_sync.csv`.
- **Browser:** the offset is estimated from the shortest of 8 round-trip pings, and again every 2 minutes.
- **LSL streams:** mapped with LSL's own clock synchronisation.
- **BLE and serial:** timestamped on arrival (latency of a few milliseconds).
