"""Counterbalancing, task subsets and the menu click models (no browser needed)."""

import collections
import itertools

import pytest

from hci import config, counterbalance, menus, tasks
from hci.tasks import NUMBER, index_pages


@pytest.fixture(scope="module")
def cfg():
    return config.load()


SUBSETS = counterbalance.SUBSETS


# ------------------------------------------------------------------------------ counterbalancing
def complete_set(emotions=("x", "y"), menu_ids=("a", "b", "c")):
    return [counterbalance.assign(f"P{n:02d}", list(emotions), list(menu_ids)) for n in range(1, 7)]


def cells(plan):
    return [(b["emotion"], s["menu"], s["subset"]) for b in plan["blocks"] for s in b["sub_blocks"]]


def test_six_participants_are_one_complete_balanced_set():
    plans = complete_set()
    combos = {(tuple(p["emotion_order"]), tuple(p["menu_order"])) for p in plans}
    assert len(combos) == 6                                          # every emotion order x menu order exactly once
    for k in range(2):
        assert collections.Counter(p["emotion_order"][k] for p in plans) == {"x": 3, "y": 3}
    for pos in range(3):
        assert collections.Counter(p["menu_order"][pos] for p in plans) == {"a": 2, "b": 2, "c": 2}
    assert counterbalance.assign("P07", ["x", "y"], ["a", "b", "c"]) == {**plans[0], "participant_number": 7}


def test_the_same_menu_order_is_used_in_both_emotion_blocks():
    for p in complete_set():
        orders = [[s["menu"] for s in b["sub_blocks"]] for b in p["blocks"]]
        assert orders[0] == orders[1] == p["menu_order"]


def test_every_participant_meets_every_subset_once():
    for p in complete_set():
        assert sorted(s for _, _, s in cells(p)) == SUBSETS


def test_every_cell_sees_every_subset_once_across_a_complete_set():
    by_cell = collections.defaultdict(list)
    for p in complete_set():
        for emotion, menu, subset in cells(p):
            by_cell[(emotion, menu)].append(subset)
    assert len(by_cell) == 6
    assert all(sorted(v) == SUBSETS for v in by_cell.values())


def test_each_subset_is_paired_equally_with_each_menu_and_emotion():
    menu_pairs, emotion_pairs = collections.Counter(), collections.Counter()
    for p in complete_set():
        for emotion, menu, subset in cells(p):
            menu_pairs[(subset, menu)] += 1
            emotion_pairs[(subset, emotion)] += 1
    assert set(menu_pairs.values()) == {2} and len(menu_pairs) == 18
    assert set(emotion_pairs.values()) == {3} and len(emotion_pairs) == 12


def test_practice_follows_the_participants_menu_order():
    for p in complete_set():
        assert [x["menu"] for x in p["practice"]] == p["menu_order"]


@pytest.mark.parametrize("pid", ["1", "P1", "p01", "P00", "PX1"])
def test_bad_participant_ids_are_rejected(pid):
    with pytest.raises(ValueError):
        counterbalance.participant_number(pid)


def test_the_plan_is_deterministic_for_every_group(cfg):
    for gid, g in cfg.groups.items():
        a = counterbalance.assign("P04", g["emotions"], g["menus"])
        assert a == counterbalance.assign("P04", g["emotions"], g["menus"])
        assert {s["menu"] for b in a["blocks"] for s in b["sub_blocks"]} == set(g["menus"])


# ------------------------------------------------------------------------------ menus
def test_every_group_has_three_menus_and_menus_are_nested(cfg):
    assert [m for g in cfg.groups.values() for m in g["menus"]] == [f"M{i}" for i in range(1, 10)]
    for gid, g in cfg.groups.items():
        assert all(cfg.menus[m]["group"] == gid for m in g["menus"])
    assert len({m["type"] for m in cfg.menus.values()}) == 9


# fewest-clicks range of the fastest path to one page, over every menu state (documented in MENUS.md)
DOCUMENTED_CLICKS = {"M1": (1, 1), "M2": (1, 2), "M3": (2, 2), "M4": (2, 2), "M5": (2, 2), "M6": (1, 1),
                     "M7": (3, 3), "M8": (2, 2), "M9": (1, 2)}


def test_click_models_match_the_documented_ranges(cfg):
    sections = [s["id"] for s in config.load_site(cfg.group("G1")["site"])["sections"]]
    for mid, expected in DOCUMENTED_CLICKS.items():
        assert menus.click_range(cfg.menu(mid)["type"], sections) == expected, mid


def test_persistent_menus_reward_a_second_page_in_the_same_section():
    assert menus.shortest("sidebar-tree", ["finance/tuition", "finance/refunds"]) == (3, 3)
    assert menus.shortest("sidebar-tree", ["finance/tuition", "services/library"]) == (4, 4)
    assert menus.shortest("hub-spoke", ["finance/tuition", "finance/refunds"]) == (4, 4)
    assert menus.shortest("hover-dropdown", ["finance/tuition"]) == (1, 2)


# ------------------------------------------------------------------------------ task subsets
def specs(cfg, gid):
    task_cfg = config.load_tasks(cfg.group(gid)["tasks"])
    return task_cfg, {k: task_cfg[k] for k in SUBSETS}


def test_every_subset_has_the_same_type_mix_in_the_same_order(cfg):
    for gid in cfg.groups:
        task_cfg, subsets = specs(cfg, gid)
        assert sorted(task_cfg) == sorted([*SUBSETS, "P"])
        mixes = {tuple(t["type"] for t in s) for s in subsets.values()}
        assert mixes == {("lookup", "extreme", "lookup", "compare")}, (gid, mixes)


def test_compare_tasks_always_need_two_different_pages(cfg):
    for gid in cfg.groups:
        for name, subset in specs(cfg, gid)[1].items():
            compare = subset[3]
            assert len({x["page"] for x in compare["items"]}) == 2, (gid, name)


def test_every_task_resolves_with_a_valid_answer_in_both_wordings(cfg):
    for gid, group in cfg.groups.items():
        site = config.load_site(group["site"])
        task_cfg = config.load_tasks(group["tasks"])
        for subset, variant in itertools.product(SUBSETS, (None, "repetitive")):
            block = tasks.build_subset(site, task_cfg, subset, variant, seed=3)
            assert len(block) == 4
            for t in block:
                assert t["answer"] in t["options"], (gid, t["id"])
                assert len(set(t["options"])) == len(t["options"]) >= 2, (gid, t["id"])
                assert "answer" not in tasks.client_view(t)


def test_extreme_and_compare_answers_have_a_clear_margin(cfg):
    """'Which is cheapest / has most votes' must not hinge on a near-tie (>= 8 %)."""
    for gid, group in cfg.groups.items():
        site = config.load_site(group["site"])
        pages = index_pages(site)
        for subset in SUBSETS:
            for spec in config.load_tasks(group["tasks"])[subset]:
                if spec["type"] == "extreme":
                    pairs = [(i, spec["field"]) for i in pages[spec["page"]]["items"]]
                elif spec["type"] == "compare":
                    pairs = [(next(i for i in pages[x["page"]]["items"] if i["name"] == x["item"]), x.get("field", spec["field"]))
                             for x in spec["items"]]
                else:
                    continue
                values = sorted(float(NUMBER.search(i["values"][f]).group().replace(",", "")) for i, f in pairs)
                best, second = (values[-1], values[-2]) if spec["mode"] == "max" else (values[0], values[1])
                assert abs(best - second) / max(abs(best), abs(second), 1) >= 0.08, (site["id"], spec["id"], values)


def test_practice_pool_never_targets_a_page_used_by_a_subset(cfg):
    for gid, group in cfg.groups.items():
        site = config.load_site(group["site"])
        task_cfg = config.load_tasks(group["tasks"])
        used = {p for s in SUBSETS for t in tasks.build_subset(site, task_cfg, s) for p in t["targets"]}
        practice = tasks.build_subset(site, task_cfg, "P")
        assert len(practice) >= 6
        assert all(t["type"] == "lookup" for t in practice)
        assert not used & {p for t in practice for p in t["targets"]}, gid
        sections = [t["targets"][0].split("/")[0] for t in practice[:6]]
        assert all(sections[i] != sections[i + 1] for i in (0, 2, 4)), "the two practice tasks of a menu use different sections"


def test_every_subset_is_solvable_from_every_menu_of_its_group(cfg):
    """Each target page exists and each of the group's menus has a finite path to it (the model of each menu's
    own rules). The same pages are reached in the real menus by tests/test_subsets_browser.py."""
    for gid, group in cfg.groups.items():
        site = config.load_site(group["site"])
        task_cfg = config.load_tasks(group["tasks"])
        pages = set(index_pages(site))
        for subset in [*SUBSETS, "P"]:
            for mid in group["menus"]:
                for t in tasks.build_subset(site, task_cfg, subset, seed=1, menu_type=cfg.menu(mid)["type"]):
                    assert set(t["targets"]) <= pages
                    assert 1 <= t["shortest_clicks"] <= t["shortest_steps"] + 3, (gid, subset, mid, t["id"])


def test_subsets_are_difficulty_matched_by_navigation_cost(cfg):
    """Within a group, every menu needs about the same navigation effort for each subset."""
    for gid, group in cfg.groups.items():
        site = config.load_site(group["site"])
        task_cfg = config.load_tasks(group["tasks"])
        for mid in group["menus"]:
            totals = []
            for subset in SUBSETS:
                built = tasks.build_subset(site, task_cfg, subset, seed=1, menu_type=cfg.menu(mid)["type"])
                totals.append(sum(t["shortest_clicks"] for t in built))
            assert max(totals) - min(totals) <= 4, (gid, mid, totals)


def test_sites_have_six_by_six_structure(cfg):
    for group in cfg.groups.values():
        site = config.load_site(group["site"])
        assert len(site["sections"]) == 6
        assert all(len(s["pages"]) == 6 for s in site["sections"])
        per_page = [[i["id"] for i in p["items"]] for s in site["sections"] for p in s["pages"]]
        assert all(len(x) == len(set(x)) for x in per_page)


# ------------------------------------------------------------------------------ the check command
def test_check_covers_menus_tasks_and_session_length_and_no_sensors(cfg):
    from hci import preflight
    rows = preflight.run(lenient=True)
    by_name = {name: (level, msg) for name, level, msg in rows}
    assert not any("sensor" in n or n in ("eye_tracker", "gsr", "hr") for n in by_name), "check must not test sensors"
    for mid in cfg.menus:
        assert by_name[f"menu {mid}"][0] == "ok", mid
    for gid in cfg.groups:
        assert by_name[f"{gid} tasks"][0] == "ok", by_name[f"{gid} tasks"]
        assert by_name[f"{gid} session length"][0] == "ok", by_name[f"{gid} session length"]      # worst case within 55 min
    assert by_name["config"][0] == "ok"


def test_planned_session_length_is_about_fifty_minutes_or_less(cfg):
    for gid in cfg.groups:
        typical, worst = __import__("hci.preflight", fromlist=["x"]).estimate_minutes(cfg, gid)
        assert 38 <= typical <= 52 and typical < worst <= 55, (gid, typical, worst)
