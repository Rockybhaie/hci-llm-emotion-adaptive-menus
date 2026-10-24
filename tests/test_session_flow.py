"""A simulated participant walks through a whole session over the real HTTP API (mock sensors)."""

import json
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


def make(tmp_path, group="G2", pid="P01", **kw):
    s = Session(config.load(), group, pid, mock=True, fast=True, pilot=True, data_root=tmp_path, **kw)
    s.start_sensors()
    s.wait_for_samples(5)
    return s, TestClient(create_app(s))


def answer_data(step):
    t = step["type"]
    if t == "consent":
        return {"agreed": True}
    if t == "demographics":
        return {"age": "24", "gender": "Woman", "handedness": "Right", "vision": "No",
                "computer_hours": "3–6", "site_familiarity": "Weekly", "caffeine_2h": "No"}
    if t == "rating":
        inst = step["params"]["instruments"]
        return {"sam": SAM, "emotions": EMO, **({"tlx": TLX} if "tlx" in inst else {})}
    if t == "calibration":
        return {"status": "success", "error": 0.01, "attempts": 1}
    if t == "debrief":
        return {"retain_data": "yes"}
    return {}


def run_tasks(client, session, step, n_tasks=4):
    started = []
    for task in step["params"]["tasks"][:n_tasks]:
        started.append(task["id"])
        client.post("/api/task/start", json={"task_id": task["id"], "t": now()})
        section, page = task["targets"][0].split("/")
        events = [
            {"t": now(), "task_id": task["id"], "source": "site", "event": "menu_open", "section": section},
            {"t": now(), "task_id": task["id"], "source": "site", "event": "click", "x": 0.3, "y": 0.1},
            {"t": now(), "task_id": task["id"], "source": "site", "event": "page_view", "section": "x", "page": "wrong"},
            {"t": now(), "task_id": task["id"], "source": "site", "event": "page_view", "section": section, "page": page},
        ]
        aoi = [{"t": now(), "snapshot": 1, "kind": "menu",
                "rects": [{"id": f"nav:{section}", "x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0}]}]
        mouse = [[now(), 0.4, 0.2], [now() + 0.01, 0.42, 0.21]]
        assert client.post("/api/log", json={"events": events, "mouse": mouse, "aoi": aoi}).json()["ok"]
        time.sleep(0.05)
        real = next(t for b in session.blocks for t in b["tasks"] if t["id"] == task["id"])
        r = client.post("/api/task/answer", json={"task_id": task["id"], "answer": real["answer"], "t": now()}).json()
        assert r["correct"] is True
    return {"started": started}


def walk(client, session, decline=False, withdraw=False):
    info = client.get("/api/session").json()
    shown = [t for s in info["steps"] if s["type"] == "tasks" for t in s["params"]["tasks"]]
    assert shown and all("answer" not in t for t in shown)  # answers never reach the browser
    assert all(e not in json.dumps(info["steps"]) for e in ("frustration", "boredom"))   # nor emotion names
    for step in info["steps"]:
        i = step["index"]
        assert client.post("/api/step/start", json={"index": i, "t": now()}).json()["ok"]
        if step["type"] == "end":
            break
        if step["type"] == "calibration":
            for action in ("start", "point", "compute", "stop"):
                assert client.post(f"/api/calibration/{action}", json={"x": 0.5, "y": 0.5}).json()["ok"]
        data = answer_data(step)
        if step["type"] == "tasks":
            data = run_tasks(client, session, step)
        if step["type"] == "consent" and decline:
            data = {"agreed": False}
        if step["type"] == "debrief" and withdraw:
            data = {"retain_data": "withdraw"}
        time.sleep(0.1)
        assert client.post("/api/step/complete", json={"index": i, "t": now(), "data": data}).json()["ok"]
        if step["type"] == "consent" and decline:
            client.post("/api/abort", json={"reason": "consent declined"})
            assert session.done.wait(10)
            return
    assert session.done.wait(10)


def test_full_session_writes_every_file(tmp_path):
    session, client = make(tmp_path)
    walk(client, session)
    folder = tmp_path / "G2" / "P01"
    for name in ("session.json", "markers.csv", "events.csv", "mouse.csv", "aoi.csv", "tasks.csv",
                 "questionnaires.csv", "gaze.csv", "gsr.csv", "hr.csv", "merged.csv"):
        assert (folder / name).exists(), name
    info = json.loads((folder / "session.json").read_text())
    assert info["status"] == "complete"
    assert info["progress"]["completed_steps"][-1] == len(session.steps) - 1

    tasks = pd.read_csv(folder / "tasks.csv")
    answered = tasks[tasks.outcome == "correct"]
    assert len(answered) == 8 and len(tasks) == 24                 # 4 answered + 8 not reached, per block
    assert (answered.wrong_pages == 1).all() and (answered.menu_opens == 1).all()
    assert set(tasks.emotion) == {"frustration", "boredom"}
    assert tasks[tasks.emotion == "boredom"].task_id.str.endswith("R").all()

    q = pd.read_csv(folder / "questionnaires.csv")
    assert set(q.instrument) >= {"consent", "demographics", "sam", "emotions", "tlx", "debrief"}
    assert len(q[q.instrument == "tlx"]) == 12

    merged = pd.read_csv(folder / "merged.csv", keep_default_na=False)
    assert {"baseline", "induction", "tasks", "rating", "washout"} <= set(merged.phase)
    assert {"frustration", "boredom", "neutral"} <= set(merged.emotion)
    assert (merged.task_id != "").any()
    assert merged.gsr_us.replace("", None).dropna().astype(float).gt(0).all()
    assert merged.gaze_aoi.str.startswith("menu:").any()


def test_existing_participant_is_refused(tmp_path):
    session, client = make(tmp_path, pid="P02")
    session._save()
    session.finish("aborted")
    with pytest.raises(SessionExists):
        Session(config.load(), "G2", "P02", mock=True, fast=True, pilot=True, data_root=tmp_path)


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
