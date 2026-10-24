import itertools

import pytest

from hci import config, counterbalance, tasks
from hci.sensors.polar_h10 import parse_heart_rate
from hci.sensors.shimmer import gsr_raw_to_microsiemens
from hci.tasks import NUMBER, index_pages


@pytest.fixture(scope="module")
def cfg():
    return config.load()


def test_counterbalance_is_balanced_every_four_participants():
    emotions = ["x", "y"]
    plans = [counterbalance.assign(f"P{n:02d}", emotions) for n in range(1, 9)]
    combos = [tuple((b["emotion"], b["task_set"]) for b in p["blocks"]) for p in plans[:4]]
    assert len(set(combos)) == 4
    firsts = [p["blocks"][0]["emotion"] for p in plans[:4]]
    assert firsts.count("x") == firsts.count("y") == 2
    assert plans[0] == plans[4]


@pytest.mark.parametrize("pid", ["1", "P1", "p01", "P00", "PX1"])
def test_bad_participant_ids_are_rejected(pid):
    with pytest.raises(ValueError):
        counterbalance.participant_number(pid)


def test_every_task_resolves_with_a_valid_answer(cfg):
    for gid, group in cfg.groups.items():
        site = config.load_site(group["site"])
        task_cfg = config.load_tasks(group["tasks"])
        for task_set, variant in itertools.product("AB", (None, "repetitive")):
            block = tasks.build_block(site, task_cfg, task_set, variant, seed=3)
            assert len(block) == 12
            for t in block:
                assert t["answer"] in t["options"], (gid, t["id"])
                assert len(set(t["options"])) == len(t["options"]), (gid, t["id"])
                assert len(t["options"]) >= 2
                assert "answer" not in tasks.client_view(t)


def test_parallel_sets_have_the_same_task_types(cfg):
    for group in cfg.groups.values():
        task_cfg = config.load_tasks(group["tasks"])
        assert [t["type"] for t in task_cfg["A"]] == [t["type"] for t in task_cfg["B"]]


def test_extreme_and_compare_answers_have_a_clear_margin(cfg):
    """'Which is cheapest / has most votes' must not hinge on a near-tie."""
    for group in cfg.groups.values():
        site = config.load_site(group["site"])
        pages = index_pages(site)
        for spec in config.load_tasks(group["tasks"])["A"] + config.load_tasks(group["tasks"])["B"]:
            if spec["type"] == "extreme":
                items = pages[spec["page"]]["items"]
            elif spec["type"] == "compare":
                items = [next(i for i in pages[x["page"]]["items"] if i["name"] == x["item"]) for x in spec["items"]]
            else:
                continue
            values = sorted(float(NUMBER.search(i["values"][spec["field"]]).group().replace(",", ""))
                            for i in items)
            best, second = (values[-1], values[-2]) if spec["mode"] == "max" else (values[0], values[1])
            assert abs(best - second) / max(abs(best), abs(second), 1) >= 0.08, (site["id"], spec["id"], values)


def test_sites_have_six_by_six_structure(cfg):
    for group in cfg.groups.values():
        site = config.load_site(group["site"])
        assert len(site["sections"]) == 6
        assert all(len(s["pages"]) == 6 for s in site["sections"])
        ids = [i["id"] for s in site["sections"] for p in s["pages"] for i in p["items"]]
        per_page = [[i["id"] for i in p["items"]] for s in site["sections"] for p in s["pages"]]
        assert all(len(x) == len(set(x)) for x in per_page)
        assert ids


def test_polar_heart_rate_parsing():
    # flags: uint8 HR + RR present; HR 72; RR 1024/1024 s and 512/1024 s
    data = bytes([0x10, 72, 0x00, 0x04, 0x00, 0x02])
    assert parse_heart_rate(data) == (72, [1000, 500])
    # uint16 HR, no RR
    assert parse_heart_rate(bytes([0x01, 0x2C, 0x01])) == (300, [])


def test_shimmer_gsr_conversion_is_positive():
    raw = (1 << 14) | 2000   # range 1, mid-scale ADC
    assert gsr_raw_to_microsiemens(raw) > 0
