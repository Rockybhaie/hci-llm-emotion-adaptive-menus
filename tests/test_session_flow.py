"""A simulated participant walks through whole sessions over the real HTTP API (no browser)."""

import json
import re
import time

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from hci import config
from hci.clock import now
from hci.server import create_app
from hci.session import Session, SessionExists

SAM = {"valence": 5, "arousal": 6, "dominance": 4}
EMO = {k: 3 for k in ["stressed", "calm", "frustrated", "bored", "happy", "sad"]}
TLX = {k: 50 for k in ["mental", "physical", "temporal", "performance", "effort", "frustration"]}
TLX_SHORT = {"mental": 40, "effort": 55, "frustration": 20}
VIEWPORT = {"innerWidth": 1000, "innerHeight": 500, "screenWidth": 1000, "screenHeight": 500}
LABELS = ["phase", "emotion_block", "emotion", "sub_block", "menu_id", "menu_type"]


def make(tmp_path, group="G2", pid="P01", **kw):
    s = Session(config.load(), group, pid, fast=True, pilot=True, data_root=tmp_path, **kw)
    s._save()
    client = TestClient(create_app(s))
    client.post("/api/client-info", json=VIEWPORT)
    return s, client


def answer_data(step):
    t = step["type"]
    if t == "consent":
        return {"agreed": True}
    if t == "demographics":
        return {"age": "24", "gender": "Woman", "handedness": "Right", "vision": "No",
                "computer_hours": "3–6", "site_familiarity": "Weekly", "caffeine_2h": "No"}
    if t == "rating":
        inst = step["params"]["instruments"]
        return {"sam": SAM, "emotions": EMO, **({"tlx": TLX} if "tlx" in inst else {}),
                **({"tlx_short": TLX_SHORT} if "tlx_short" in inst else {})}
    if t == "menu_rank":
        return {"ranks": {m["id"]: i + 1 for i, m in enumerate(step["params"]["menus"])}}
    if t == "debrief":
        return {"retain_data": "yes"}
    return {}


def run_tasks(client, session, index, n_tasks=None, answer_correctly=True):
    """Do the step's tasks the way a person would: open the menu, click, pass a wrong page twice, reach the target."""
    step = session.steps[index]
    started = []
    for task in step["tasks_full"][:n_tasks]:
        tid = task["id"]
        started.append(tid)
        client.post("/api/task/start", json={"task_id": tid, "t": now()})
        section, page = task["targets"][0].split("/")
        ev = lambda name, **kw: {"t": now(), "task_id": tid, "source": "site", "event": name, **kw}
        opened = [
            ev("menu_open", section=section, detail={"state": f"open:{section}", "panel": section}),
            ev("click", x=0.3, y=0.1, detail={"target": f"nav:{section}"}),
            ev("click", x=0.3, y=0.2, detail={"target": f"item:{section}/{page}"}),
        ]
        t0 = now()
        mouse = [[t0 + 0.01, 0.1, 0.1], [t0 + 0.02, 0.6, 0.1]]            # 0.5 of 1000 px = 500 px
        aoi = [{"t": now(), "snapshot": 1, "kind": "menu",
                "rects": [{"id": f"nav:{section}", "x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0}]}]
        assert client.post("/api/log", json={"events": opened, "mouse": mouse, "aoi": aoi}).json()["ok"]
        time.sleep(0.25)                                                    # the menu stays open for a moment
        closed = [
            ev("menu_close", section=section, detail={"state": "closed", "reason": "select"}),
            ev("page_view", section="x", page="wrong"),
            ev("page_view", section="x", page="wrong"),
            ev("backtrack", section="x", page="wrong"),
            ev("page_view", section=section, page=page),
        ]
        assert client.post("/api/log", json={"events": closed}).json()["ok"]
        reply = task["answer"] if answer_correctly else next(o for o in task["options"] if o != task["answer"])
        r = client.post("/api/task/answer", json={"task_id": tid, "answer": reply, "t": now()}).json()
        assert r["correct"] is answer_correctly
    return {"started": started}


def walk(client, session, decline=False, withdraw=False, until=None):
    """Complete every step from the session's current one; stop (without completing) at index `until`."""
    info = client.get("/api/session").json()
    for step in info["steps"][session.current:]:
        i = step["index"]
        if until is not None and i == until:
            return
        assert client.post("/api/step/start", json={"index": i, "t": now()}).json()["ok"]
        if step["type"] == "end":
            break
        client.post("/api/log", json={"events": [{"t": now(), "source": "shell", "event": "step",
                                                    "detail": {"index": i, "type": step["type"]}}]})
        data = answer_data(step)
        if step["type"] in ("tasks", "practice"):
            data = run_tasks(client, session, i)
        if step["type"] == "consent" and decline:
            data = {"agreed": False}
        if step["type"] == "debrief" and withdraw:
            data = {"retain_data": "withdraw"}
        time.sleep(0.13)                    # a step shorter than one 100 ms bin would not appear in merged.csv
        assert client.post("/api/step/complete", json={"index": i, "t": now(), "data": data}).json()["ok"]
        if step["type"] == "consent" and decline:
            client.post("/api/abort", json={"reason": "consent declined"})
            assert session.done.wait(10)
            return
    assert session.done.wait(10)


def index_of(session, type_, emotion_block=None, sub_block=None):
    return next(s["index"] for s in session.steps
                if s["type"] == type_ and s["emotion_block"] == emotion_block and s["sub_block"] == sub_block)


# ------------------------------------------------------------------------------ a whole session
@pytest.mark.parametrize("group,pid", [("G1", "P01"), ("G2", "P08"), ("G3", "P03")])
def test_full_session_writes_every_file_with_every_label(tmp_path, group, pid):
    session, client = make(tmp_path, group, pid)
    info = client.get("/api/session").json()

    # nothing the participant must not see reaches the browser
    for s in info["steps"]:
        for t in s["params"].get("tasks", []):
            assert "answer" not in t
    visible = json.dumps([s["params"] for s in info["steps"]])
    visible = re.sub(r"/stimuli/[\w./-]+", "", visible)                    # file names are not shown to participants
    assert not re.search(r"\b(frustration|boredom|stress|joy|sadness)\b", visible, re.I), "emotion name sent to the browser"

    walk(client, session)
    folder = tmp_path / group / pid
    for name in ("session.json", "plan.json", "plan.txt", "markers.csv", "events.csv", "mouse.csv", "aoi.csv", "tasks.csv",
                 "questionnaires.csv", "subblocks.csv", "merged.csv"):
        assert (folder / name).exists(), name
    assert not any((folder / f"{n}.csv").exists() for n in ("gaze", "gsr", "hr", "clock_sync")), "sensor files must not exist"
    state = json.loads((folder / "session.json").read_text())
    assert state["status"] == "complete" and "devices" not in state and "calibration" not in state
    assert state["progress"]["completed_steps"][-1] == len(session.steps) - 1
    assert (folder / "plan.txt").read_text().startswith("scheme ")

    plan = session.plan
    tasks_df = pd.read_csv(folder / "tasks.csv", keep_default_na=False)
    for col in LABELS + ["subset", "attempt", "correct", "shortest_clicks", "shortest_steps", "mouse_path_px",
                         "menu_clicks", "backtracks"]:
        assert col in tasks_df.columns, col
    practice = tasks_df[tasks_df.phase == "practice"]
    real = tasks_df[tasks_df.phase == "tasks"]
    assert len(practice) == 6 and len(real) == 24
    assert list(practice.menu_id.unique()) == plan["menu_order"]            # practice follows the participant's menu order
    assert (tasks_df.correct == 1).all() and (tasks_df.attempt == 1).all()
    expected = [(b["no"], s["sub_block"], s["menu"], s["subset"]) for b in plan["blocks"] for s in b["sub_blocks"]]
    got = [(int(a), int(b), c, d) for (a, b, c, d), _ in real.groupby(["emotion_block", "sub_block", "menu_id", "subset"], sort=False)]
    assert got == expected
    assert (real.groupby(["emotion_block", "sub_block"]).size() == 4).all()
    assert (real.menu_clicks == 2).all() and (real.menu_opens == 1).all() and (real.wrong_pages == 2).all()
    assert (real.backtracks == 1).all() and (real.page_views == 3).all()
    assert ((real.mouse_path_px - 500).abs() < 1).all()
    assert pd.to_numeric(real.shortest_clicks).ge(1).all()
    assert set(real.emotion) == set(session.group["emotions"]) and set(practice.emotion) == {"neutral"}
    boredom = real[real.emotion == "boredom"]
    assert boredom.empty or boredom.task_id.str.endswith("R").all()

    events = pd.read_csv(folder / "events.csv", keep_default_na=False)
    for col in LABELS:
        assert col in events.columns
    assert {"practice", "tasks", "booster", "induction", "rating", "menu_rank"} <= set(events.phase)
    assert set(events[events.phase == "practice"].menu_id) == set(session.group["menus"])
    assert (events[(events.phase == "tasks")].sub_block != "").all()
    markers = pd.read_csv(folder / "markers.csv", keep_default_na=False)
    assert {"practice", "booster", "menu_rank"} <= set(markers.phase)

    q = pd.read_csv(folder / "questionnaires.csv", keep_default_na=False)
    assert set(q.instrument) >= {"consent", "demographics", "sam", "emotions", "tlx_short", "menu_rank", "debrief"}
    assert {f"subblock_{b}_{s}" for b in (1, 2) for s in (1, 2, 3)} <= set(q.tag)
    assert len(q[q.instrument == "tlx_short"]) == 6 * 3                     # 6 sub-blocks x 3 items
    sub_ratings = q[q.tag.str.startswith("subblock_") & (q.instrument == "emotions")]
    assert len(sub_ratings) == 6 * 6                                        # always all six emotion items, every sub-block
    assert set(sub_ratings.menu_id) == set(session.group["menus"]) and (sub_ratings.sub_block != "").all()

    sub = pd.read_csv(folder / "subblocks.csv")
    assert len(sub) == 6 and sub.accuracy.eq(1.0).all() and sub.attempt.eq(1).all()
    assert list(sub.menu_id) == [m for _, _, m, _ in expected]
    for col in ("mood_stressed", "mood_sad", "tlx_mental", "tlx_effort", "tlx_frustration", "menu_rank", "excess_menu_clicks"):
        assert col in sub.columns and sub[col].notna().all(), col
    assert (sub.tlx_effort == 55).all() and sorted(sub[sub.emotion_block == 1].menu_rank) == [1, 2, 3]

    merged = pd.read_csv(folder / "merged.csv", keep_default_na=False)
    assert list(merged.columns) == ["t", "t_rel", "step", *LABELS, "task_id", "menu_state", "mouse_x", "mouse_y", "mouse_dist",
                                    "clicks", "menu_events", "page_views", "backtracks", "sabotage"]
    assert {"baseline", "practice", "induction", "booster", "tasks", "rating", "washout", "menu_rank"} <= set(merged.phase)
    assert set(merged.emotion) >= {"neutral", *session.group["emotions"]}
    assert (merged.task_id != "").any()
    states = set(merged[merged.phase.isin(["tasks", "practice"])].menu_state)
    assert "closed" in states and any(s.startswith("open:") for s in states)
    assert (merged[~merged.phase.isin(["tasks", "practice"])].menu_state == "").all()


def test_export_combines_every_table_with_the_new_columns(tmp_path):
    from hci import export
    for group, pid in (("G1", "P01"), ("G3", "P02")):
        session, client = make(tmp_path, group, pid)
        walk(client, session)
    sessions, written = export.export_all(root=tmp_path, out=tmp_path / "exports", rebuild=True)
    names = {p.name for p in written}
    assert names == {"dataset_all.csv", "tasks_all.csv", "subblocks_all.csv", "events_all.csv", "questionnaires_all.csv", "sessions.csv"}
    out = tmp_path / "exports"
    tasks_all = pd.read_csv(out / "tasks_all.csv")
    assert list(tasks_all.columns[:2]) == ["group", "participant"] and set(tasks_all.group) == {"G1", "G3"}
    assert {"menu_id", "menu_type", "sub_block", "emotion_block", "subset"} <= set(tasks_all.columns)
    sub = pd.read_csv(out / "subblocks_all.csv")
    assert len(sub) == 12 and set(sub.menu_id) == {"M1", "M2", "M3", "M7", "M8", "M9"}
    sess = pd.read_csv(out / "sessions.csv")
    assert set(sess.status) == {"complete"} and {"emotion_order", "menu_order", "scheme"} <= set(sess.columns)
    assert not any(c.startswith(("gaze", "gsr", "hr_", "pupil")) for c in pd.read_csv(out / "dataset_all.csv", nrows=1).columns)


def test_existing_participant_is_refused(tmp_path):
    session, client = make(tmp_path, pid="P02")
    session.finish("aborted")
    with pytest.raises(SessionExists):
        Session(config.load(), "G2", "P02", fast=True, pilot=True, data_root=tmp_path)


def test_declined_consent_keeps_nothing(tmp_path):
    session, client = make(tmp_path, group="G1", pid="P03")
    walk(client, session, decline=True)
    assert not (tmp_path / "G1" / "P03").exists()


def test_withdrawal_at_debrief_deletes_data(tmp_path):
    session, client = make(tmp_path, group="G3", pid="P04")
    walk(client, session, withdraw=True)
    assert session.status == "withdrawn"
    assert not (tmp_path / "G3" / "P04").exists()


def test_out_of_order_steps_are_rejected(tmp_path):
    session, client = make(tmp_path, pid="P05")
    assert client.post("/api/step/start", json={"index": 3}).json()["ok"] is False
    session.finish("aborted")


# ------------------------------------------------------------------------------ resume at sub-block level
def test_resume_restarts_the_interrupted_subblock_and_uses_its_last_attempt(tmp_path):
    session, client = make(tmp_path, "G1", "P02")
    stop = index_of(session, "tasks", 1, 2)                                 # emotion block 1, sub-block 2
    walk(client, session, until=stop)
    assert session.current == stop
    client.post("/api/step/start", json={"index": stop, "t": now()})
    run_tasks(client, session, stop, n_tasks=2)                             # two of four tasks, then the power cut
    session.abort("test")
    assert (tmp_path / "G1" / "P02" / "subblocks.csv").exists()

    session2 = Session(config.load(), "G1", "P02", fast=True, pilot=True, resume=True, data_root=tmp_path)
    assert session2.current == stop and session2.attempts[stop] == 2
    assert any("Resumed" in m for _, m in session2.warnings)
    client2 = TestClient(create_app(session2))
    client2.post("/api/client-info", json=VIEWPORT)
    walk(client2, session2)

    folder = tmp_path / "G1" / "P02"
    tasks_df = pd.read_csv(folder / "tasks.csv")
    sb = tasks_df[(tasks_df.phase == "tasks") & (tasks_df.emotion_block == 1) & (tasks_df.sub_block == 2)]
    assert sorted(sb.attempt.unique()) == [1, 2]
    assert (sb.attempt == 1).sum() == 2 and (sb.attempt == 2).sum() == 4
    other = tasks_df[(tasks_df.phase == "tasks") & ~((tasks_df.emotion_block == 1) & (tasks_df.sub_block == 2))]
    assert (other.attempt == 1).all() and len(other) == 20
    summary = pd.read_csv(folder / "subblocks.csv")
    row = summary[(summary.emotion_block == 1) & (summary.sub_block == 2)].iloc[0]
    assert row.attempt == 2 and row.tasks_total == 4
    assert len(summary) == 6
    markers = pd.read_csv(folder / "markers.csv", keep_default_na=False)
    assert "resumed" in set(markers.event)
    assert json.loads((folder / "session.json").read_text())["status"] == "complete"


def test_resume_refuses_a_changed_plan(tmp_path):
    session, client = make(tmp_path, "G2", "P06")
    session.abort("test")
    path = tmp_path / "G2" / "P06" / "session.json"
    saved = json.loads(path.read_text())
    saved["plan"]["menu_order"] = list(reversed(saved["plan"]["menu_order"]))      # as if config/groups.yaml changed
    path.write_text(json.dumps(saved))
    with pytest.raises(config.ConfigError, match="counterbalancing plan"):
        Session(config.load(), "G2", "P06", fast=True, pilot=True, resume=True, data_root=tmp_path)
