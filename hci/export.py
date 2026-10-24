"""Build model-ready tables.

merged.csv (per session): one row per 100 ms with the phase / emotion / task
labels, sensor values, gaze area-of-interest and behaviour counts.
data/exports/: every completed session stacked into one file per table.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import paths

BIN_S = 0.1
AOI_PRIORITY = ("menu", "taskbar", "content")


def _read(folder, name):
    path = folder / f"{name}.csv"
    if not path.exists() or path.stat().st_size == 0:
        return None
    df = pd.read_csv(path)
    return df if len(df) else None


def _bin_index(t, t0):
    return np.floor((np.asarray(t, dtype=float) - t0) / BIN_S).astype(int)


def _labels(grid, markers):
    starts = markers[markers["event"].isin(["start", "resumed"])].sort_values("t")
    starts = starts.drop_duplicates("step", keep="last")[["t", "step", "phase", "block", "emotion"]]
    grid = pd.merge_asof(grid, starts, on="t", direction="backward")
    grid["phase"] = grid["phase"].fillna("setup")    # sensors running, participant not started yet
    return grid


def _task_ids(grid, tasks):
    if tasks is None:
        grid["task_id"] = ""
        return grid
    done = tasks.dropna(subset=["t_start", "t_end"]).sort_values("t_start")
    if done.empty:
        grid["task_id"] = ""
        return grid
    m = pd.merge_asof(grid[["t"]], done[["t_start", "t_end", "task_id"]], left_on="t", right_on="t_start",
                      direction="backward")
    grid["task_id"] = np.where(m["t"] <= m["t_end"], m["task_id"], "")
    return grid


def _gaze(grid, gaze, t0):
    if gaze is None:
        return grid
    lv, rv = gaze["left_valid"] == 1, gaze["right_valid"] == 1
    gx = pd.concat([gaze["left_x"].where(lv), gaze["right_x"].where(rv)], axis=1).mean(axis=1)
    gy = pd.concat([gaze["left_y"].where(lv), gaze["right_y"].where(rv)], axis=1).mean(axis=1)
    pupil = pd.concat([gaze["left_pupil"].where(gaze["left_pupil_valid"] == 1),
                       gaze["right_pupil"].where(gaze["right_pupil_valid"] == 1)], axis=1).mean(axis=1)
    g = pd.DataFrame({"bin": _bin_index(gaze["t"], t0), "gaze_x": gx, "gaze_y": gy, "pupil_mm": pupil,
                      "gaze_valid": (lv | rv).astype(float)})
    agg = g.groupby("bin").mean()
    return grid.join(agg, on="bin")


def _signal(grid, df, column, t0, how):
    if df is None or column not in df:
        grid[column] = np.nan
        return grid
    s = pd.DataFrame({"bin": _bin_index(df["t"], t0), column: pd.to_numeric(df[column], errors="coerce")})
    agg = s.groupby("bin")[column].agg(how)
    grid[column] = grid["bin"].map(agg)
    grid[column] = grid[column].ffill()
    return grid


def _mouse(grid, mouse, t0):
    if mouse is None:
        return grid
    mouse = mouse.sort_values("t")
    dist = np.hypot(mouse["x"].diff(), mouse["y"].diff()).fillna(0)
    m = pd.DataFrame({"bin": _bin_index(mouse["t"], t0), "mouse_x": mouse["x"], "mouse_y": mouse["y"],
                      "mouse_dist": dist})
    agg = m.groupby("bin").agg(mouse_x=("mouse_x", "last"), mouse_y=("mouse_y", "last"),
                               mouse_dist=("mouse_dist", "sum"))
    grid = grid.join(agg, on="bin")
    grid[["mouse_x", "mouse_y"]] = grid[["mouse_x", "mouse_y"]].ffill()
    grid["mouse_dist"] = grid["mouse_dist"].fillna(0)
    return grid


def _events(grid, events, t0):
    cols = {"clicks": lambda e: e == "click",
            "menu_events": lambda e: e.str.startswith("menu_"),
            "page_views": lambda e: e == "page_view",
            "sabotage": lambda e: e.str.startswith("sabotage_")}
    for name in cols:
        grid[name] = 0
    if events is None:
        return grid
    b = _bin_index(events["t"], t0)
    ev = events["event"].astype(str)
    for name, pick in cols.items():
        counts = pd.Series(b[pick(ev).to_numpy()]).value_counts()
        grid[name] = grid["bin"].map(counts).fillna(0).astype(int)
    return grid


def _gaze_aoi(grid, aoi):
    grid["gaze_aoi"] = ""
    if aoi is None or "gaze_x" not in grid:
        return grid
    snaps = {}  # kind -> sorted list of (t, rects)
    for (t, kind), rows in aoi.groupby(["t", "kind"], sort=True):
        rects = rows.dropna(subset=["x0"])
        rects = [(r.id, r.x0, r.y0, r.x1, r.y1) for r in rects.itertuples() if isinstance(r.id, str) and r.id]
        snaps.setdefault(kind, []).append((t, rects))
    pointers = {k: -1 for k in snaps}
    out = []
    for t, x, y in zip(grid["t"], grid["gaze_x"], grid["gaze_y"]):
        hit = ""
        for kind in AOI_PRIORITY:
            seq = snaps.get(kind)
            if not seq:
                continue
            i = pointers[kind]
            while i + 1 < len(seq) and seq[i + 1][0] <= t:
                i += 1
            pointers[kind] = i
            if hit or i < 0 or x != x:
                continue
            for rid, x0, y0, x1, y1 in seq[i][1]:
                if x0 <= x <= x1 and y0 <= y <= y1:
                    hit = rid if rid.startswith(f"{kind}:") else f"{kind}:{rid}"
                    break
        out.append(hit)
    grid["gaze_aoi"] = out
    return grid


def merge_session(folder: Path):
    folder = Path(folder)
    session = json.loads((folder / "session.json").read_text(encoding="utf-8"))
    markers = _read(folder, "markers")
    if markers is None:
        raise ValueError("no markers.csv")
    t0 = session["clock"]["t_zero"]
    t_end = markers["t"].max()
    n = int((t_end - t0) / BIN_S) + 1
    grid = pd.DataFrame({"bin": np.arange(n)})
    grid["t"] = t0 + grid["bin"] * BIN_S
    grid = _labels(grid, markers)
    grid = _task_ids(grid, _read(folder, "tasks"))
    grid = _gaze(grid, _read(folder, "gaze"), t0)
    grid = _signal(grid, _read(folder, "gsr"), "gsr_us", t0, "mean")
    grid = _signal(grid, _read(folder, "hr"), "hr_bpm", t0, "last")
    grid = _mouse(grid, _read(folder, "mouse"), t0)
    grid = _events(grid, _read(folder, "events"), t0)
    grid = _gaze_aoi(grid, _read(folder, "aoi"))
    grid.insert(1, "t_rel", (grid["bin"] * BIN_S).round(1))
    grid = grid.drop(columns=["bin"])
    order = ["t", "t_rel", "step", "phase", "block", "emotion", "task_id", "gaze_x", "gaze_y", "gaze_valid",
             "pupil_mm", "gaze_aoi", "gsr_us", "hr_bpm", "mouse_x", "mouse_y", "mouse_dist",
             "clicks", "menu_events", "page_views", "sabotage"]
    grid = grid.reindex(columns=order)
    grid["block"] = grid["block"].astype("Int64")
    grid.to_csv(folder / "merged.csv", index=False, float_format="%.5f")
    return folder / "merged.csv"


def session_folders(root=paths.DATA):
    for group in sorted(p for p in Path(root).glob("G*") if p.is_dir()):
        for participant in sorted(p for p in group.glob("P*") if p.is_dir()):
            if (participant / "session.json").exists():
                yield participant


def export_all(root=paths.DATA, out=paths.EXPORTS, rebuild=False):
    out.mkdir(parents=True, exist_ok=True)
    tables = {"dataset_all": [], "tasks_all": [], "questionnaires_all": []}
    sessions = []
    for folder in session_folders(root):
        info = json.loads((folder / "session.json").read_text(encoding="utf-8"))
        if rebuild or not (folder / "merged.csv").exists():
            merge_session(folder)
        keys = {"group": info["group"], "participant": info["participant"]}
        for table, name in (("dataset_all", "merged"), ("tasks_all", "tasks"),
                            ("questionnaires_all", "questionnaires")):
            df = _read(folder, name)
            if df is not None:
                tables[table].append(df.assign(**keys)[[*keys, *df.columns]])
        sessions.append({**keys, "status": info["status"], "scheme": info["plan"]["scheme"],
                         "block1": f"{info['blocks'][0]['emotion']}/{info['blocks'][0]['task_set']}",
                         "block2": f"{info['blocks'][1]['emotion']}/{info['blocks'][1]['task_set']}",
                         "started": info["started"], "duration_min": round(info["duration_s"] / 60, 1),
                         **{f"{slot}_samples": d.get("samples") for slot, d in info.get("devices", {}).items()}})
    written = []
    for table, frames in tables.items():
        if frames:
            pd.concat(frames, ignore_index=True).to_csv(out / f"{table}.csv", index=False)
            written.append(out / f"{table}.csv")
    pd.DataFrame(sessions).to_csv(out / "sessions.csv", index=False)
    written.append(out / "sessions.csv")
    return sessions, written
