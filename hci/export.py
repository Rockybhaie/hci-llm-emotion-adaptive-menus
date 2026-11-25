"""Model-ready tables.

merged.csv (per participant): one row per 100 ms with step / query / look labels, the facial-emotion
stream, gaze (and which answer block it falls on), mouse and event counts.
data/exports/: every participant stacked into one file per table.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import paths

BIN_S = 0.1


def _read(folder, name):
    path = folder / f"{name}.csv"
    if not path.exists() or path.stat().st_size == 0:
        return None
    df = pd.read_csv(path)
    return df if len(df) else None


def _bin(t, t0):
    return np.floor((np.asarray(t, dtype=float) - t0) / BIN_S).astype(int)


def _labels(grid, markers):
    starts = markers[markers["event"].isin(["start", "resumed"])].sort_values("t")
    starts = starts.drop_duplicates("step", keep="last")[["t", "step", "phase", "query_id"]]
    grid = pd.merge_asof(grid, starts, on="t", direction="backward")
    grid["phase"] = grid["phase"].fillna("setup")
    grid["query_id"] = grid["query_id"].fillna("")
    return grid


def _looks(grid, looks):
    grid["look"] = ""
    if looks is None:
        return grid
    lk = looks.sort_values("t")[["t", "query_id", "look"]].rename(columns={"query_id": "look_query"})
    m = pd.merge_asof(grid[["t"]], lk, on="t", direction="backward")
    same = (m["look_query"] == grid["query_id"]) & (grid["phase"] == "query")
    grid["look"] = np.where(same, m["look"].fillna(""), "")
    return grid


def _emotion(grid, emo, t0):
    cols = ["face", "valence", "arousal"] + ([c for c in emo.columns if c.startswith("p_")] if emo is not None else [])
    if emo is None:
        for c in ("face", "valence", "arousal", "emotion"):
            grid[c] = np.nan if c != "emotion" else ""
        return grid
    e = emo.copy()
    e["bin"] = _bin(e["t"], t0)
    agg = e.groupby("bin")[cols].mean(numeric_only=True)
    grid = grid.join(agg, on="bin")
    top = e.dropna(subset=["emotion"]).groupby("bin")["emotion"].agg(lambda s: s.mode().iloc[0])
    grid["emotion"] = grid["bin"].map(top).fillna("")
    return grid


def _gaze(grid, gaze, t0):
    if gaze is None:
        grid["gaze_x"] = grid["gaze_y"] = grid["gaze_valid"] = np.nan
        return grid
    if "x" in gaze:                                   # webcam (EyeTrax)
        g = pd.DataFrame({"bin": _bin(gaze["t"], t0), "gaze_x": gaze["x"], "gaze_y": gaze["y"],
                          "gaze_valid": (gaze["valid"] == 1).astype(float)})
    else:                                             # Tobii / mock: average the two eyes
        lv, rv = gaze["left_valid"] == 1, gaze["right_valid"] == 1
        gx = pd.concat([gaze["left_x"].where(lv), gaze["right_x"].where(rv)], axis=1).mean(axis=1)
        gy = pd.concat([gaze["left_y"].where(lv), gaze["right_y"].where(rv)], axis=1).mean(axis=1)
        g = pd.DataFrame({"bin": _bin(gaze["t"], t0), "gaze_x": gx, "gaze_y": gy,
                          "gaze_valid": (lv | rv).astype(float)})
    return grid.join(g.groupby("bin").mean(), on="bin")


def _mouse(grid, mouse, t0):
    if mouse is None:
        grid["mouse_x"] = grid["mouse_y"] = np.nan
        grid["mouse_dist"] = 0.0
        return grid
    mouse = mouse.sort_values("t")
    dist = np.hypot(mouse["x"].diff(), mouse["y"].diff()).fillna(0)
    m = pd.DataFrame({"bin": _bin(mouse["t"], t0), "mouse_x": mouse["x"], "mouse_y": mouse["y"], "mouse_dist": dist})
    agg = m.groupby("bin").agg(mouse_x=("mouse_x", "last"), mouse_y=("mouse_y", "last"),
                               mouse_dist=("mouse_dist", "sum"))
    grid = grid.join(agg, on="bin")
    grid[["mouse_x", "mouse_y"]] = grid[["mouse_x", "mouse_y"]].ffill()
    grid["mouse_dist"] = grid["mouse_dist"].fillna(0)
    return grid


def _events(grid, events, t0):
    picks = {"clicks": lambda e: e == "click", "scrolls": lambda e: e == "scroll",
             "look_changes": lambda e: e.isin(["look_auto", "look_manual", "look_back"])}
    for name in picks:
        grid[name] = 0
    if events is None:
        return grid
    b = _bin(events["t"], t0)
    ev = events["event"].astype(str)
    for name, pick in picks.items():
        counts = pd.Series(b[pick(ev).to_numpy()]).value_counts()
        grid[name] = grid["bin"].map(counts).fillna(0).astype(int)
    return grid


def _gaze_block(grid, aoi):
    """Which answer block (kind 'block' in aoi.csv) the gaze point falls on."""
    grid["gaze_block"] = ""
    if aoi is None or "gaze_x" not in grid:
        return grid
    blocks = aoi[aoi["kind"] == "block"]
    if blocks.empty:
        return grid
    snaps = []
    for t, rows in blocks.groupby("t", sort=True):
        rects = [(r.id, r.x0, r.y0, r.x1, r.y1) for r in rows.itertuples() if isinstance(r.id, str) and r.id]
        snaps.append((t, rects))
    out, i = [], -1
    for t, x, y in zip(grid["t"], grid["gaze_x"], grid["gaze_y"]):
        while i + 1 < len(snaps) and snaps[i + 1][0] <= t:
            i += 1
        hit = ""
        if i >= 0 and x == x:
            for rid, x0, y0, x1, y1 in snaps[i][1]:
                if x0 <= x <= x1 and y0 <= y <= y1:
                    hit = rid
                    break
        out.append(hit)
    grid["gaze_block"] = out
    return grid


def merge_session(folder: Path):
    folder = Path(folder)
    session = json.loads((folder / "session.json").read_text(encoding="utf-8"))
    markers = _read(folder, "markers")
    if markers is None:
        raise ValueError("no markers.csv")
    t0 = session["clock"]["t_zero"]
    n = int((markers["t"].max() - t0) / BIN_S) + 1
    grid = pd.DataFrame({"bin": np.arange(n)})
    grid["t"] = t0 + grid["bin"] * BIN_S
    grid = _labels(grid, markers)
    grid = _looks(grid, _read(folder, "looks"))
    grid = _emotion(grid, _read(folder, "emotion"), t0)
    grid = _gaze(grid, _read(folder, "gaze"), t0)
    grid = _gaze_block(grid, _read(folder, "aoi"))
    grid = _mouse(grid, _read(folder, "mouse"), t0)
    grid = _events(grid, _read(folder, "events"), t0)
    grid.insert(1, "t_rel", (grid["bin"] * BIN_S).round(1))
    probs = [c for c in grid.columns if c.startswith("p_")]
    order = ["t", "t_rel", "step", "phase", "query_id", "look", "face", "emotion", *probs, "valence", "arousal",
             "gaze_x", "gaze_y", "gaze_valid", "gaze_block", "mouse_x", "mouse_y", "mouse_dist",
             "clicks", "scrolls", "look_changes"]
    grid = grid.reindex(columns=order)
    grid.to_csv(folder / "merged.csv", index=False, float_format="%.5f")
    return folder / "merged.csv"


def session_folders(root=paths.DATA):
    for p in sorted(Path(root).glob("P*")):
        if p.is_dir() and (p / "session.json").exists():
            yield p


def export_all(root=paths.DATA, out=paths.EXPORTS, rebuild=False):
    out.mkdir(parents=True, exist_ok=True)
    tables = {"interactions_all": "interactions", "adaptations_all": "adaptations", "dataset_all": "merged",
              "questionnaires_all": "questionnaires"}
    frames = {k: [] for k in tables}
    sessions = []
    for folder in session_folders(root):
        info = json.loads((folder / "session.json").read_text(encoding="utf-8"))
        if rebuild or not (folder / "merged.csv").exists():
            merge_session(folder)
        for table, name in tables.items():
            df = _read(folder, name)
            if df is not None:
                if "participant" not in df:
                    df.insert(0, "participant", info["participant"])
                frames[table].append(df)
        sessions.append({"participant": info["participant"], "status": info["status"],
                         "order": ">".join(info["plan"]["order"]), "started": info["started"],
                         "duration_min": round(info["duration_s"] / 60, 1), "adaptations": info.get("adaptations", 0)})
    written = []
    for table, dfs in frames.items():
        if dfs:
            pd.concat(dfs, ignore_index=True).to_csv(out / f"{table}.csv", index=False)
            written.append(out / f"{table}.csv")
    pd.DataFrame(sessions).to_csv(out / "sessions.csv", index=False)
    written.append(out / "sessions.csv")
    return sessions, written
