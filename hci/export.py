"""Build model-ready tables.

merged.csv    (per session)  one row per 100 ms: the behavioural timeline with phase / emotion / menu /
                             sub-block / task labels, mouse position and movement, event counts and the
                             state of the menu.
subblocks.csv (per session)  one row per sub-block: performance, behaviour, mood and workload ratings and
                             the menu preference. Practice is excluded. For a sub-block that was repeated
                             after an interruption only the last attempt is used.
data/exports/                every completed session stacked into one file per table.

There are no sensor columns: sensors are handled outside this app.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import paths

BIN_S = 0.1
LABELS = ["phase", "emotion_block", "emotion", "sub_block", "menu_id", "menu_type"]
EMOTION_ITEMS = ["stressed", "calm", "frustrated", "bored", "happy", "sad"]
TLX_SHORT_ITEMS = ["mental", "effort", "frustration"]
SITE_PHASES = ("tasks", "practice")


def _read(folder, name):
    path = folder / f"{name}.csv"
    if not path.exists() or path.stat().st_size == 0:
        return None
    df = pd.read_csv(path, keep_default_na=False, na_values=[""])
    return df if len(df) else None


def _bin_index(t, t0):
    return np.floor((np.asarray(t, dtype=float) - t0) / BIN_S).astype(int)


def _labels(grid, markers):
    """Every grid row takes the labels of the latest step start (or resume) before it."""
    starts = markers[markers["event"].isin(["start", "resumed"])].sort_values("t")
    starts = starts[["t", "step", *LABELS]]
    grid = pd.merge_asof(grid, starts, on="t", direction="backward")
    grid["phase"] = grid["phase"].fillna("setup")
    for col in ("menu_id", "menu_type", "emotion"):
        grid[col] = grid[col].fillna("")
    return grid


def _task_ids(grid, tasks):
    grid["task_id"] = ""
    if tasks is None:
        return grid
    done = tasks.dropna(subset=["t_start", "t_end"]).sort_values("t_start")
    if done.empty:
        return grid
    m = pd.merge_asof(grid[["t"]], done[["t_start", "t_end", "task_id"]], left_on="t", right_on="t_start",
                      direction="backward")
    grid["task_id"] = np.where(m["t"] <= m["t_end"], m["task_id"], "")
    return grid


def _mouse(grid, mouse, t0):
    for c in ("mouse_x", "mouse_y", "mouse_dist"):
        grid[c] = np.nan
    if mouse is None:
        return grid
    mouse = mouse.sort_values("t")
    dist = np.hypot(mouse["x"].diff(), mouse["y"].diff()).fillna(0)
    m = pd.DataFrame({"bin": _bin_index(mouse["t"], t0), "mouse_x": mouse["x"], "mouse_y": mouse["y"], "mouse_dist": dist})
    agg = m.groupby("bin").agg(mouse_x=("mouse_x", "last"), mouse_y=("mouse_y", "last"), mouse_dist=("mouse_dist", "sum"))
    grid = grid.drop(columns=["mouse_x", "mouse_y", "mouse_dist"]).join(agg, on="bin")
    grid[["mouse_x", "mouse_y"]] = grid[["mouse_x", "mouse_y"]].ffill()
    grid["mouse_dist"] = grid["mouse_dist"].fillna(0)
    return grid


def _events(grid, events, t0):
    cols = {"clicks": lambda e, s: (e == "click") & (s == "site"),
            "menu_events": lambda e, s: e.isin(["menu_open", "menu_close", "item_select"]),
            "page_views": lambda e, s: e == "page_view",
            "backtracks": lambda e, s: e == "backtrack",
            "sabotage": lambda e, s: e.str.startswith("sabotage_")}
    for name in cols:
        grid[name] = 0
    if events is None:
        return grid
    b = _bin_index(events["t"], t0)
    ev = events["event"].astype(str)
    src = events["source"].astype(str)
    for name, pick in cols.items():
        counts = pd.Series(b[pick(ev, src).to_numpy()]).value_counts()
        grid[name] = grid["bin"].map(counts).fillna(0).astype(int)
    return grid


def _menu_state(grid, events):
    """'closed' / 'open:<section or panel>' while a site is on screen, '' otherwise."""
    grid["menu_state"] = ""
    on_site = grid["phase"].isin(SITE_PHASES)
    state = pd.Series("closed", index=grid.index)
    if events is not None:
        ev = events[events["event"].isin(["menu_open", "menu_close"])].sort_values("t")
        if len(ev):
            def parse(detail):
                try:
                    return json.loads(detail).get("state", "")
                except (TypeError, ValueError):
                    return ""
            s = pd.DataFrame({"t": ev["t"], "s": ev["detail"].map(parse)})
            s = s[s["s"] != ""]
            m = pd.merge_asof(grid[["t"]], s, on="t", direction="backward")
            state = m["s"].fillna("closed")
    grid.loc[on_site, "menu_state"] = state[on_site]
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
    events = _read(folder, "events")
    grid = _task_ids(grid, _read(folder, "tasks"))
    grid = _mouse(grid, _read(folder, "mouse"), t0)
    grid = _events(grid, events, t0)
    grid = _menu_state(grid, events)
    grid.insert(1, "t_rel", (grid["bin"] * BIN_S).round(1))
    grid = grid.drop(columns=["bin"])
    order = ["t", "t_rel", "step", *LABELS, "task_id", "menu_state", "mouse_x", "mouse_y", "mouse_dist",
             "clicks", "menu_events", "page_views", "backtracks", "sabotage"]
    grid = grid.reindex(columns=order)
    for col in ("emotion_block", "sub_block"):
        grid[col] = grid[col].astype("Int64")
    grid.to_csv(folder / "merged.csv", index=False, float_format="%.5f")
    return folder / "merged.csv"


def subblock_summary(folder: Path):
    """One row per sub-block (see the module docstring); returns the path, or None without task data."""
    folder = Path(folder)
    tasks = _read(folder, "tasks")
    if tasks is None:
        return None
    tasks = tasks[tasks["phase"] == "tasks"].copy()
    if tasks.empty:
        return None
    q = _read(folder, "questionnaires")
    key = ["emotion_block", "sub_block"]
    tasks["attempt"] = tasks["attempt"].fillna(1).astype(int)
    last = tasks.groupby(key)["attempt"].transform("max")
    tasks = tasks[tasks["attempt"] == last]
    sums = ["clicks", "menu_clicks", "menu_opens", "page_views", "wrong_pages", "backtracks", "sabotage_events",
            "answer_attempts", "shortest_clicks", "shortest_steps", "mouse_path_px"]
    rows = []
    for (eb, sb), g in tasks.groupby(key, sort=True):
        first = g.iloc[0]
        dur = pd.to_numeric(g["duration_s"], errors="coerce")
        row = {"emotion_block": int(eb), "emotion": first["emotion"], "sub_block": int(sb), "menu_id": first["menu_id"],
               "menu_type": first["menu_type"], "subset": first["subset"], "attempt": int(first["attempt"]),
               "tasks_total": len(g), "correct": int(g["correct"].sum()),
               "accuracy": round(g["correct"].sum() / len(g), 3),
               "timeouts": int((g["outcome"] == "timeout").sum()), "not_reached": int((g["outcome"] == "not_reached").sum()),
               "duration_sum_s": round(dur.sum(), 2), "duration_mean_s": round(dur.mean(), 2) if dur.notna().any() else np.nan,
               "duration_median_s": round(dur.median(), 2) if dur.notna().any() else np.nan,
               "duration_mean_correct_s": round(dur[g["correct"] == 1].mean(), 2) if (g["correct"] == 1).any() else np.nan}
        for c in sums:
            row[c] = round(pd.to_numeric(g[c], errors="coerce").sum(), 1) if c == "mouse_path_px" \
                else int(pd.to_numeric(g[c], errors="coerce").fillna(0).sum())
        row["excess_menu_clicks"] = row["menu_clicks"] - row["shortest_clicks"]
        if q is not None:
            tag = f"subblock_{int(eb)}_{int(sb)}"
            mine = q[q["tag"] == tag].sort_values("t")
            for item in EMOTION_ITEMS:
                v = mine[(mine["instrument"] == "emotions") & (mine["item"] == item)]["value"]
                row[f"mood_{item}"] = v.iloc[-1] if len(v) else np.nan
            for item in TLX_SHORT_ITEMS:
                v = mine[(mine["instrument"] == "tlx_short") & (mine["item"] == item)]["value"]
                row[f"tlx_{item}"] = v.iloc[-1] if len(v) else np.nan
            ranks = q[(q["tag"] == f"menu_rank_{int(eb)}") & (q["item"] == first["menu_id"])].sort_values("t")["value"]
            row["menu_rank"] = ranks.iloc[-1] if len(ranks) else np.nan
        rows.append(row)
    out = pd.DataFrame(rows)
    out.to_csv(folder / "subblocks.csv", index=False)
    return folder / "subblocks.csv"


def session_folders(root=paths.DATA):
    for group in sorted(p for p in Path(root).glob("G*") if p.is_dir()):
        for participant in sorted(p for p in group.glob("P*") if p.is_dir()):
            if (participant / "session.json").exists():
                yield participant


def export_all(root=paths.DATA, out=paths.EXPORTS, rebuild=False):
    out.mkdir(parents=True, exist_ok=True)
    tables = {"dataset_all": [], "tasks_all": [], "subblocks_all": [], "events_all": [], "questionnaires_all": []}
    sources = {"dataset_all": "merged", "tasks_all": "tasks", "subblocks_all": "subblocks", "events_all": "events",
               "questionnaires_all": "questionnaires"}
    sessions = []
    for folder in session_folders(root):
        info = json.loads((folder / "session.json").read_text(encoding="utf-8"))
        if rebuild or not (folder / "merged.csv").exists():
            merge_session(folder)
        if rebuild or not (folder / "subblocks.csv").exists():
            subblock_summary(folder)
        keys = {"group": info["group"], "participant": info["participant"]}
        for table, name in sources.items():
            df = _read(folder, name)
            if df is not None:
                tables[table].append(df.assign(**keys)[[*keys, *df.columns]])
        plan = info["plan"]
        sessions.append({**keys, "status": info["status"], "scheme": plan["scheme"],
                         "emotion_order": ">".join(plan["emotion_order"]), "menu_order": ">".join(plan["menu_order"]),
                         "started": info["started"], "duration_min": round(info["duration_s"] / 60, 1)})
    written = []
    for table, frames in tables.items():
        if frames:
            pd.concat(frames, ignore_index=True).to_csv(out / f"{table}.csv", index=False)
            written.append(out / f"{table}.csv")
    pd.DataFrame(sessions).to_csv(out / "sessions.csv", index=False)
    written.append(out / "sessions.csv")
    return sessions, written
