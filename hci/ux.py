"""UX indicators for the seven UX goals of the menus (see docs/ux-mapping.md).

ux_tasks.csv     (per session)  one row per task, practice included: the per-task indicators.
ux_subblocks.csv (per session)  one row per sub-block, i.e. one menu in one emotion. Practice is excluded and
                                only the last attempt of a repeated sub-block is used.
ux_menus.csv     (per session)  one row per menu: the headline indicator of every goal, pooled over both
                                emotion blocks. Learnability and memorability exist only here, because they
                                compare practice, emotion block 1 and emotion block 2.

Everything is computed from tasks.csv, events.csv and questionnaires.csv; nothing extra is logged.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .export import EMOTION_ITEMS, LABELS, _read

UNEXPECTED_CLOSE = {"leave"}     # the menu closed by itself (M1's hover drop-down); 'glitch' is an induced fault
EVENT_COLUMNS = ["t", "task_id", "event", "section", "page", "detail"]
TASK_COLUMNS = [*LABELS, "subset", "attempt", "task_id", "type", "use_no", "t_start",
                "correct", "timeout", "target_reached", "nav_failure",                        # effective
                "time_to_target_s", "lag_removed_s", "time_per_step_s", "lostness",          # efficient
                "mouse_path_px",
                "page_views", "wrong_pages", "wrong_page_rate", "backtracks", "unexpected_closes"]   # safe


def _detail(text):
    try:
        return json.loads(text) if isinstance(text, str) and text else {}
    except ValueError:
        return {}


def _num(x):
    return pd.to_numeric(x, errors="coerce")


def _mean(values):
    v = _num(pd.Series(values, dtype=object))
    return round(float(v.mean()), 3) if v.notna().any() else np.nan


def _ratio(a, b):
    return round(float(a) / float(b), 3) if pd.notna(a) and pd.notna(b) and b > 0 else np.nan


def _last_attempt(tasks):
    """Keep only the last attempt of a step that was repeated after --resume."""
    key = ["phase", "emotion_block", "sub_block", "menu_id"]
    return tasks[tasks["attempt"] == tasks.groupby(key, dropna=False)["attempt"].transform("max")]


def _rating(q, tag, instrument, item):
    if q is None:
        return np.nan
    v = q[(q["tag"] == tag) & (q["instrument"] == instrument) & (q["item"] == item)].sort_values("t")["value"]
    return _num(v.iloc[-1]) if len(v) else np.nan


# ------------------------------------------------------------------ per task
def _task_events(events, task):
    """One task's events: its task id, inside its time window (a repeated sub-block reuses task ids)."""
    if pd.isna(task["t_start"]):
        return events.iloc[0:0]
    t1 = task["t_end"] if pd.notna(task["t_end"]) else np.inf
    ev = events[(events["task_id"] == task["task_id"]) & events["t"].between(task["t_start"], t1)]
    return ev.sort_values("t", kind="stable")


def task_indicators(task, events):
    ev = _task_events(events, task)
    targets = set(str(task["target_pages"]).split(";"))
    views = ev[ev["event"] == "page_view"]
    pages = [f"{s}/{p}" for s, p in zip(views["section"], views["page"])]

    # time to target: until every target page has been shown, minus induced page lag before that moment
    reached_at, seen = np.nan, set()
    for t, page in zip(views["t"], pages):
        seen.add(page)
        if targets <= seen:
            reached_at = t
            break
    reached = pd.notna(reached_at)
    lag_s = 0.0
    if reached:
        lags = ev[(ev["event"] == "sabotage_lag") & (ev["t"] < reached_at)]
        lag_s = sum(_detail(d).get("ms", 0) for d in lags["detail"]) / 1000
    ttt = reached_at - task["t_start"] - lag_s if reached else np.nan

    # Smith (1996) lostness: S page views, N distinct pages, R pages required
    s, n, r = len(pages), len(set(pages)), len(targets)
    lostness = round(float(np.sqrt((n / s - 1) ** 2 + (r / n - 1) ** 2)), 3) if s else np.nan

    closes = ev[ev["event"] == "menu_close"]
    correct = int(task["correct"])
    return {
        **{c: task[c] for c in [*LABELS, "subset", "attempt", "task_id", "type", "t_start"]},
        "correct": correct, "timeout": int(task["outcome"] == "timeout"),
        "target_reached": int(reached), "nav_failure": int(not correct and not reached),
        "time_to_target_s": round(ttt, 3) if reached else np.nan, "lag_removed_s": round(lag_s, 3),
        "time_per_step_s": _ratio(ttt, _num(task["shortest_steps"])), "lostness": lostness,
        "mouse_path_px": task["mouse_path_px"],
        "page_views": task["page_views"], "wrong_pages": task["wrong_pages"],
        "wrong_page_rate": _ratio(_num(task["wrong_pages"]), _num(task["page_views"])),
        "backtracks": task["backtracks"],
        "unexpected_closes": sum(_detail(d).get("reason") in UNEXPECTED_CLOSE for d in closes["detail"]),
    }


# ------------------------------------------------------------------ per sub-block (one menu, one emotion)
def _by_type(g, col, kind):
    return _mean(g.loc[g["type"] == kind, col])


def subblock_indicators(g, q):
    first = g.iloc[0]
    eb, sb = int(first["emotion_block"]), int(first["sub_block"])
    lookup, compare = _by_type(g, "time_per_step_s", "lookup"), _by_type(g, "time_per_step_s", "compare")
    row = {
        "emotion_block": eb, "emotion": first["emotion"], "sub_block": sb, "menu_id": first["menu_id"],
        "menu_type": first["menu_type"], "subset": first["subset"], "attempt": int(first["attempt"]), "tasks_total": len(g),
        # effective
        "success_rate": _mean(g["correct"]), "target_reached_rate": _mean(g["target_reached"]),
        "nav_failure_rate": _mean(g["nav_failure"]), "timeout_rate": _mean(g["timeout"]),
        # efficient
        "time_to_target_s": _mean(g["time_to_target_s"]), "time_per_step_s": _mean(g["time_per_step_s"]),
        "lostness": _mean(g["lostness"]), "mouse_path_px": _mean(g["mouse_path_px"]),
        # safe
        "wrong_page_rate": _ratio(_num(g["wrong_pages"]).sum(), _num(g["page_views"]).sum()),
        "backtracks": int(_num(g["backtracks"]).sum()), "unexpected_closes": int(g["unexpected_closes"].sum()),
        # good utility
        "time_per_step_lookup_s": lookup, "time_per_step_extreme_s": _by_type(g, "time_per_step_s", "extreme"),
        "time_per_step_compare_s": compare, "compare_ratio": _ratio(compare, lookup),
        "success_compare": _by_type(g, "correct", "compare"),
        # enjoyable
        "menu_rank": _rating(q, f"menu_rank_{eb}", "menu_rank", first["menu_id"]),
        "tlx_frustration": _rating(q, f"subblock_{eb}_{sb}", "tlx_short", "frustration"),
    }
    for item in EMOTION_ITEMS:          # change since the emotion block's post-induction rating
        row[f"mood_change_{item}"] = (_rating(q, f"subblock_{eb}_{sb}", "emotions", item)
                                      - _rating(q, f"post_induction_{eb}", "emotions", item))
    return row


# ------------------------------------------------------------------ per menu (both emotion blocks)
def menu_indicators(menu_id, all_tasks, tasks, subs):
    mine = tasks[tasks["menu_id"] == menu_id]
    practice, real = mine[mine["phase"] == "practice"], mine[mine["phase"] == "tasks"]
    lookups = real[real["type"] == "lookup"]
    first = all_tasks[(all_tasks["menu_id"] == menu_id) & (all_tasks["use_no"] == 1)]
    tps_practice = _mean(practice["time_per_step_s"])
    tps_block1 = _mean(lookups.loc[lookups["emotion_block"] == 1, "time_per_step_s"])
    tps_block2 = _mean(lookups.loc[lookups["emotion_block"] == 2, "time_per_step_s"])
    improvement = _ratio(tps_block1, tps_practice)
    s = subs[subs["menu_id"] == menu_id]
    return {
        "menu_id": menu_id, "menu_type": mine["menu_type"].iloc[0],
        "success_rate": _mean(real["correct"]),                                             # effective
        "time_to_target_s": _mean(real["time_to_target_s"]),                                # efficient
        "wrong_page_rate": _ratio(_num(real["wrong_pages"]).sum(), _num(real["page_views"]).sum()),   # safe
        "compare_ratio": _ratio(_mean(real.loc[real["type"] == "compare", "time_per_step_s"]),      # good utility
                                _mean(lookups["time_per_step_s"])),
        "first_use_time_to_target_s": _mean(first["time_to_target_s"]),                     # learnable
        "first_use_wrong_pages": _mean(first["wrong_pages"]),
        "learning_gain": round(1 - improvement, 3) if pd.notna(improvement) else np.nan,
        "relearn_ratio": _ratio(tps_block2, tps_block1),                                    # memorable
        "menu_rank_mean": _mean(s["menu_rank"]),                                            # enjoyable
        "tlx_frustration_mean": _mean(s["tlx_frustration"]),
    }


def ux_summary(folder: Path):
    """Write ux_tasks.csv, ux_subblocks.csv and ux_menus.csv; returns the paths written (None without task data)."""
    folder = Path(folder)
    tasks = _read(folder, "tasks")
    if tasks is None:
        return None
    events = _read(folder, "events")
    if events is None:
        events = pd.DataFrame(columns=EVENT_COLUMNS)
    tasks["attempt"] = _num(tasks["attempt"]).fillna(1).astype(int)

    per_task = pd.DataFrame([task_indicators(t, events) for _, t in tasks.iterrows()])
    for col in ("emotion_block", "sub_block"):
        per_task[col] = _num(per_task[col]).astype("Int64")
    order = per_task[per_task["t_start"].notna()].sort_values("t_start", kind="stable")
    per_task["use_no"] = (order.groupby("menu_id").cumcount() + 1).reindex(per_task.index).astype("Int64")
    per_task = per_task[TASK_COLUMNS]
    per_task.to_csv(folder / "ux_tasks.csv", index=False)
    written = [folder / "ux_tasks.csv"]

    real = _last_attempt(per_task[per_task["phase"] == "tasks"])
    if real.empty:
        return written
    q = _read(folder, "questionnaires")
    subs = pd.DataFrame([subblock_indicators(g, q) for _, g in real.groupby(["emotion_block", "sub_block"], sort=True)])
    subs.to_csv(folder / "ux_subblocks.csv", index=False)

    pool = pd.concat([_last_attempt(per_task[per_task["phase"] == "practice"]), real])
    menus = list(dict.fromkeys(order["menu_id"]))
    pd.DataFrame([menu_indicators(m, per_task, pool, subs) for m in menus if m in set(real["menu_id"])]) \
        .to_csv(folder / "ux_menus.csv", index=False)
    return [*written, folder / "ux_subblocks.csv", folder / "ux_menus.csv"]
