import collections
import json
import random
import time

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from hci import adapt, config, content, counterbalance
from hci.clock import now
from hci.sensing import Sensing, planned
from hci.server import create_app
from hci.session import Session, SessionExists


@pytest.fixture(scope="module")
def cfg():
    return config.load()


# ------------------------------------------------------------------ content
def test_every_query_has_all_looks_and_a_valid_quiz(cfg):
    for q in cfg.queries:
        data = content.validate(q, cfg.looks)
        assert data["quiz"]["answer"] in data["quiz"]["options"]
        assert "answer" not in content.client_view(q, cfg.looks)["quiz"]
        for look in cfg.looks:
            assert content.word_count(data["looks"][look]) >= 30, (q, look)


def test_the_five_queries_cover_five_ui_types(cfg):
    qs = [content.load_query(q) for q in cfg.queries]
    assert sorted(q["type"] for q in qs) == sorted({"comparison", "concept", "cause-effect", "plan", "calculation"})
    assert len({q["subject"] for q in qs}) == 5           # five different subjects, not five ML questions


def test_bad_tables_are_rejected():
    with pytest.raises(config.ConfigError):
        content.validate_block({"type": "table", "columns": ["a", "b"], "rows": [["1", "2", "3"]]}, "x")


# ------------------------------------------------------------------ counterbalancing
def test_query_order_is_a_latin_square(cfg):
    plans = [counterbalance.assign(f"P{n:02d}", cfg.queries, cfg.looks) for n in range(1, 6)]
    for pos in range(5):
        assert {p["order"][pos] for p in plans} == set(cfg.queries)


def test_every_query_starts_in_every_look_once_per_six(cfg):
    plans = [counterbalance.assign(f"P{n:02d}", cfg.queries, cfg.looks) for n in range(1, 7)]
    for q in cfg.queries:
        assert {p["start_looks"][q] for p in plans} == set(cfg.looks)
    for p in plans:
        assert len(set(p["start_looks"].values())) == len(cfg.queries)


# ------------------------------------------------------------------ adaptation rule
def _samples(t0, t1, negative, hz=10, face=True):
    out = []
    t = t0
    while t <= t1:
        p = {"anger": 0.3, "sad": 0.4, "neutral": 0.1, "happy": 0.05} if negative else \
            {"anger": 0.02, "sad": 0.03, "neutral": 0.8, "happy": 0.15}
        out.append({"t": t, "face": int(face), "emotion": "sad" if negative else "neutral",
                    "valence": -0.5 if negative else 0.1, "arousal": 0.2,
                    **{f"p_{c}": p.get(c, 0.0) for c in ("anger", "contempt", "disgust", "fear", "happy", "neutral", "sad", "surprise")}})
        t += 1 / hz
    return out


def test_sustained_negative_face_triggers_one_switch_to_an_unseen_look(cfg):
    a = adapt.QueryAdapter(cfg.adaptation, cfg.looks, "text", random.Random(1))
    to, snap = a.should_switch(_samples(100, 104.5, negative=True), 104.5)
    assert to in cfg.looks and to != "text"
    assert snap["negative_fraction"] == 1.0 and snap["dominant"] == "sad"
    a.switched(to, 104.5, auto=True)
    # cooldown: still negative a few seconds later, no switch
    assert a.should_switch(_samples(100, 110, negative=True), 110)[0] is None


def test_neutral_face_short_frown_or_no_face_do_not_trigger(cfg):
    a = adapt.QueryAdapter(cfg.adaptation, cfg.looks, "text")
    assert a.should_switch(_samples(100, 104.5, negative=False), 104.5)[0] is None
    assert a.should_switch(_samples(102.5, 104.5, negative=True), 104.5)[0] is None      # only 2 s of frown
    assert a.should_switch(_samples(100, 104.5, negative=True, face=False), 104.5)[0] is None


def test_at_most_two_auto_switches_and_no_repeats(cfg):
    a = adapt.QueryAdapter(cfg.adaptation, cfg.looks, "text", random.Random(3))
    t = 100.0
    seen = ["text"]
    for _ in range(4):
        t += 30
        to, _ = a.should_switch(_samples(t - 4.5, t, negative=True), t)
        if to:
            assert to not in seen
            seen.append(to)
            a.switched(to, t, auto=True)
    assert a.n_auto == cfg.adaptation["max_auto_per_query"]


# ------------------------------------------------------------------ a whole session over the HTTP API
def make(tmp_path, cfg, pid="P01"):
    plan = planned(cfg.devices, mode="mock")
    s = Session(cfg, pid, fast=True, pilot=True, data_root=tmp_path, sensor_plan=plan)
    sensing = Sensing(s.store, mode="mock", devices=cfg.devices)
    sensing.start()
    s.attach_sensing(sensing)
    return s, TestClient(create_app(s))


def walk(client, session, *, frown_first=True, withdraw=False, decline=False):
    info = client.get("/api/session").json()
    shown = [st["params"]["query"] for st in info["steps"] if st["type"] == "query"]
    assert len(shown) == 5 and all("answer" not in q["quiz"] for q in shown)
    for st in info["steps"]:
        i, kind, p = st["index"], st["type"], st["params"]
        assert client.post("/api/step/start", json={"index": i, "t": now()}).json()["ok"]
        if kind == "end":
            break
        data = {}
        if kind == "consent":
            data = {"agreed": not decline}
        elif kind == "demographics":
            data = {"age": "21", "programme": "Data Science / AI", "study_confidence": "Somewhat"}
        elif kind == "calibration":
            for action in ("start", "point", "compute", "stop"):
                client.post(f"/api/calibration/{action}", json={"x": 0.5, "y": 0.5})
            data = {"status": "success", "error": 0.03, "attempts": 1}
        elif kind == "query":
            q = p["query"]["id"]
            client.post("/api/query/look", json={"query_id": q, "look": p["start_look"], "reason": "initial", "t": now()})
            client.post("/api/log", json={"events": [{"t": now(), "event": "ask"}], "mouse": [[now(), 0.4, 0.5]],
                                          "aoi": [{"t": now(), "snapshot": 1, "kind": "block",
                                                   "rects": [{"id": "block:x:1:heading", "x0": 0, "y0": 0, "x1": 1, "y1": 1}]}]})
            if frown_first and p["position"] == 1:
                assert client.post("/api/pilot/frown").json()["ok"]
                sw = None
                deadline = time.time() + 12
                while sw is None and time.time() < deadline:
                    time.sleep(0.3)
                    sw = client.post("/api/adapt/poll", json={"query_id": q}).json()["switch"]
                assert sw, "a simulated frown must trigger an automatic switch"
                client.post("/api/query/look", json={"query_id": q, "look": sw["to"], "reason": "auto",
                                                     "adaptation_id": sw["id"], "t": now()})
                assert client.post("/api/adapt/resolve", json={"id": sw["id"], "response": "keep", "t": now()}).json()["ok"]
            other = next(lk["id"] for lk in p["looks"] if lk["id"] not in session.active.adapter.seen)
            r = client.post("/api/adapt/manual", json={"query_id": q, "to": other}).json()
            assert r["ok"]
            client.post("/api/query/look", json={"query_id": q, "look": other, "reason": "manual",
                                                 "adaptation_id": r["id"], "t": now()})
            time.sleep(0.2)
            data = {"ratings": {"satisfaction": 6, "preferred": other},
                    "quiz_answer": content.load_query(q)["quiz"]["answer"], "t_done": now()}
        elif kind == "final":
            data = {"favourite_look": "visual", "comment": "nice"}
        elif kind == "debrief":
            data = {"retain_data": "withdraw" if withdraw else "yes"}
        assert client.post("/api/step/complete", json={"index": i, "t": now(), "data": data}).json()["ok"]
        if kind == "consent" and decline:
            client.post("/api/abort", json={"reason": "consent declined"})
            break
    assert session.done.wait(15)


def test_full_session_writes_the_dataset(tmp_path, cfg):
    session, client = make(tmp_path, cfg)
    walk(client, session)
    folder = tmp_path / "P01"
    for name in ("session.json", "markers.csv", "events.csv", "looks.csv", "interactions.csv", "adaptations.csv",
                 "questionnaires.csv", "emotion.csv", "gaze.csv", "mouse.csv", "aoi.csv", "merged.csv"):
        assert (folder / name).exists(), name

    inter = pd.read_csv(folder / "interactions.csv")
    assert len(inter) == 5 and set(inter.query_id) == set(cfg.queries)
    assert (inter.quiz_correct == 1).all() and (inter.satisfaction == 6).all()
    first = inter[inter.position == 1].iloc[0]
    assert first.n_auto == 1 and first.n_kept == 1 and first.n_manual == 1 and first.n_looks == 3
    assert (inter.emotion_samples > 0).all()

    ad = pd.read_csv(folder / "adaptations.csv")
    auto = ad[ad.trigger == "auto"]
    assert len(auto) == 1 and auto.iloc[0].response == "keep"
    assert auto.iloc[0].before_negative_fraction >= cfg.adaptation["min_fraction"]
    assert len(ad[ad.trigger == "manual"]) == 5 and (ad[ad.trigger == "manual"].response == "chosen").all()

    merged = pd.read_csv(folder / "merged.csv", keep_default_na=False)
    assert "query" in set(merged.phase)          # (steps the bot finishes in milliseconds fill no 100 ms bin)
    q_rows = merged[merged.phase == "query"]
    assert (q_rows.query_id != "").all() and (q_rows.look != "").mean() > 0.9
    assert merged.emotion.replace("", None).notna().any()
    info = json.loads((folder / "session.json").read_text())
    assert info["status"] == "complete" and set(info["content"]) == set(cfg.queries)


def test_existing_participant_is_refused(tmp_path, cfg):
    session, _ = make(tmp_path, cfg, "P02")
    session._save()
    session.finish("aborted")
    with pytest.raises(SessionExists):
        Session(cfg, "P02", fast=True, pilot=True, data_root=tmp_path)


def test_withdrawal_and_declined_consent_delete_everything(tmp_path, cfg):
    s, c = make(tmp_path, cfg, "P03")
    walk(c, s, frown_first=False, withdraw=True)
    assert s.status == "withdrawn" and not (tmp_path / "P03").exists()
    s, c = make(tmp_path, cfg, "P04")
    walk(c, s, decline=True)
    assert not (tmp_path / "P04").exists()


def test_frown_hotkey_only_in_pilot(tmp_path, cfg):
    s = Session(cfg, "P05", fast=True, pilot=False, data_root=tmp_path)
    assert s.pilot_frown()["ok"] is False
    s.finish("aborted")
