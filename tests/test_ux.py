"""UX indicators (hci/ux.py) on a hand-made participant folder whose answers can be worked out by hand."""

import json

import numpy as np
import pandas as pd
import pytest

from hci.ux import ux_summary


def task(phase, eb, sb, tid, type_, targets, t0, steps, correct=1, page_views=1, wrong=0, attempt=1):
    return {"phase": phase, "emotion_block": eb, "emotion": "stress" if eb else "neutral", "sub_block": sb,
            "menu_id": "M1", "menu_type": "hover-dropdown", "subset": "S1" if eb else "P", "attempt": attempt,
            "task_id": tid, "type": type_, "target_pages": targets, "t_start": t0, "t_end": t0 + 30,
            "outcome": "correct" if correct else "incorrect", "correct": correct, "shortest_steps": steps,
            "mouse_path_px": 100.0, "page_views": page_views, "wrong_pages": wrong, "backtracks": 0}


def ev(t, tid, event, section="", page="", **detail):
    return {"t": t, "task_id": tid, "source": "site", "event": event, "section": section, "page": page,
            "detail": json.dumps(detail) if detail else ""}


def q(tag, instrument, item, value):
    return {"t": 0, "tag": tag, "instrument": instrument, "item": item, "value": value}


@pytest.fixture
def folder(tmp_path):
    tasks = [
        task("practice", None, None, "P1", "lookup", "a/b", 0, 2),                         # tps 4/2 = 2.0
        task("tasks", 1, 1, "S1-1", "lookup", "a/b", 100, 2, page_views=2, wrong=1),     # tps 3/2 = 1.5 (lag removed)
        task("tasks", 1, 1, "S1-4", "compare", "a/b;c/d", 200, 2, correct=0, page_views=1),   # never reached c/d
        task("tasks", 2, 1, "S4-1", "lookup", "a/b", 300, 2, attempt=1),                 # superseded attempt
        task("tasks", 2, 1, "S4-1", "lookup", "a/b", 400, 2, attempt=2),                 # tps 6/2 = 3.0
    ]
    events = [
        ev(4, "P1", "page_view", "a", "b"),
        ev(101, "S1-1", "page_view", "x", "y"),
        ev(103, "S1-1", "sabotage_lag", ms=2000),
        ev(105, "S1-1", "page_view", "a", "b"),
        ev(106, "S1-1", "menu_close", reason="leave"),
        ev(107, "S1-1", "menu_close", reason="select"),
        ev(202, "S1-4", "page_view", "a", "b"),
        ev(301, "S4-1", "page_view", "a", "b"),                                          # attempt 1, not counted
        ev(406, "S4-1", "page_view", "a", "b"),
    ]
    ratings = [
        q("post_induction_1", "emotions", "happy", 3), q("subblock_1_1", "emotions", "happy", 5),
        q("subblock_1_1", "tlx_short", "frustration", 40), q("menu_rank_1", "menu_rank", "M1", 1),
        q("menu_rank_2", "menu_rank", "M1", 3),
    ]
    pd.DataFrame(tasks).to_csv(tmp_path / "tasks.csv", index=False)
    pd.DataFrame(events).to_csv(tmp_path / "events.csv", index=False)
    pd.DataFrame(ratings).to_csv(tmp_path / "questionnaires.csv", index=False)
    ux_summary(tmp_path)
    return tmp_path


def test_task_indicators(folder):
    t = pd.read_csv(folder / "ux_tasks.csv").set_index(["task_id", "attempt"])
    lookup = t.loc[("S1-1", 1)]
    assert lookup.time_to_target_s == pytest.approx(3.0) and lookup.lag_removed_s == pytest.approx(2.0)
    assert lookup.time_per_step_s == pytest.approx(1.5)
    assert lookup.lostness == pytest.approx(0.5)            # S = 2, N = 2, R = 1
    assert lookup.wrong_page_rate == pytest.approx(0.5) and lookup.unexpected_closes == 1
    compare = t.loc[("S1-4", 1)]
    assert compare.target_reached == 0 and np.isnan(compare.time_to_target_s) and compare.nav_failure == 1
    assert t.loc[("S4-1", 2)].time_to_target_s == pytest.approx(6.0)  # events of attempt 1 are ignored
    assert list(t.sort_values("t_start").use_no) == [1, 2, 3, 4, 5]


def test_subblock_indicators(folder):
    s = pd.read_csv(folder / "ux_subblocks.csv").set_index("emotion_block")
    assert list(s.attempt) == [1, 2]                         # only the last attempt of block 2
    b1 = s.loc[1]
    assert b1.success_rate == 0.5 and b1.target_reached_rate == 0.5 and b1.nav_failure_rate == 0.5
    assert b1.wrong_page_rate == round(1 / 3, 3)             # 1 wrong page of 3 page views
    assert np.isnan(b1.compare_ratio)                        # the compare never reached its targets
    assert b1.menu_rank == 1 and b1.tlx_frustration == 40 and b1.mood_change_happy == 2
    assert s.loc[2].menu_rank == 3


def test_menu_indicators(folder):
    m = pd.read_csv(folder / "ux_menus.csv").iloc[0]
    assert m.menu_id == "M1"
    assert m.first_use_time_to_target_s == pytest.approx(4.0)
    assert m.learning_gain == pytest.approx(0.25)            # 1 - 1.5 / 2.0
    assert m.relearn_ratio == pytest.approx(2.0)             # 3.0 / 1.5
    assert m.menu_rank_mean == 2 and m.success_rate == round(2 / 3, 3)
