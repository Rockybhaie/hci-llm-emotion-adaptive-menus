"""Generate the neutral washout clip: slowly drifting abstract shapes on a mid-grey background.

Modelled on the "Abstract Shapes" neutral film of Gross & Levenson (1995): coloured geometric
shapes moving slowly, with no people, no story and no sound. Being generated, it is identical
for every participant and needs no licence.

    python stimuli/make_neutral.py            # writes stimuli/videos/neutral.webm (150 s)
"""

import argparse
import math
import random
from pathlib import Path

import cv2
import numpy as np

W, H, FPS = 1280, 720, 30
BACKGROUND = (150, 150, 150)                       # mid-grey, close to the resting-baseline screen
PALETTE = [(176, 132, 112), (120, 150, 176), (128, 168, 136), (180, 160, 120),
           (150, 130, 165), (120, 165, 170), (170, 140, 140), (140, 140, 175)]   # muted BGR


def shape_points(kind, cx, cy, r, angle):
    n = {"triangle": 3, "square": 4, "pentagon": 5, "hexagon": 6}[kind]
    return np.array([[cx + r * math.cos(angle + 2 * math.pi * i / n),
                      cy + r * math.sin(angle + 2 * math.pi * i / n)] for i in range(n)], np.int32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=150)
    ap.add_argument("--out", default=str(Path(__file__).parent / "videos" / "neutral.webm"))
    args = ap.parse_args()

    rng = random.Random(1995)
    shapes = []
    for i in range(14):
        speed = rng.uniform(18, 40)                    # pixels per second: slow
        heading = rng.uniform(0, 2 * math.pi)
        shapes.append({
            "kind": rng.choice(["circle", "triangle", "square", "pentagon", "hexagon"]),
            "x": rng.uniform(100, W - 100), "y": rng.uniform(100, H - 100),
            "vx": speed * math.cos(heading), "vy": speed * math.sin(heading),
            "r": rng.uniform(30, 75), "angle": rng.uniform(0, math.pi), "spin": rng.uniform(-0.25, 0.25),
            "color": PALETTE[i % len(PALETTE)],
        })

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"VP80"), FPS, (W, H))
    if not writer.isOpened():
        raise SystemExit("OpenCV cannot write VP8 video on this machine")
    dt = 1 / FPS
    for _ in range(args.seconds * FPS):
        frame = np.full((H, W, 3), BACKGROUND, np.uint8)
        for s in shapes:
            s["x"] += s["vx"] * dt
            s["y"] += s["vy"] * dt
            s["angle"] += s["spin"] * dt
            if not s["r"] < s["x"] < W - s["r"]:
                s["vx"] *= -1
            if not s["r"] < s["y"] < H - s["r"]:
                s["vy"] *= -1
            if s["kind"] == "circle":
                cv2.circle(frame, (int(s["x"]), int(s["y"])), int(s["r"]), s["color"], -1, cv2.LINE_AA)
            else:
                cv2.fillPoly(frame, [shape_points(s["kind"], s["x"], s["y"], s["r"], s["angle"])],
                             s["color"], cv2.LINE_AA)
        writer.write(frame)
    writer.release()
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
