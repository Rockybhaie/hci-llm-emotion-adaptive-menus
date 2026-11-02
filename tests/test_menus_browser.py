"""The nine real menus, driven in Edge (skipped when Playwright / Edge is missing).

What is proved here
  * every menu reaches pages through its own rules (the plan() each menu publishes is executed with a real mouse)
  * all menus emit the same event vocabulary, and the backtrack definition holds in each
  * every menu always shows a Home control and exposes item rectangles
  * the emotion faults live in the engine and behave the same in every menu
"""

import re
from pathlib import Path

import pytest

from browser_support import MenuPage
from hci import config, paths

CFG = config.load()
ALL = [(gid, mid) for gid, g in CFG.groups.items() for mid in g["menus"]]
IDS = [f"{gid}-{mid}" for gid, mid in ALL]

REQUIRED = {"menu_open", "menu_close", "item_hover_enter", "item_hover_exit", "item_select", "page_view", "backtrack"}
ALLOWED = REQUIRED | {"search_query", "home_view", "click", "scroll", "click_while_loading"}


@pytest.fixture(params=ALL, ids=IDS)
def mp(request, browser, base_url):
    gid, mid = request.param
    page = MenuPage(browser, base_url, gid, mid)
    yield page
    page.close()


def one_page_per_section(site):
    return [(s["id"], s["pages"][i % 6]["id"]) for i, s in enumerate(site["sections"])]


def test_every_menu_reaches_pages_through_its_own_rules(mp):
    for section, page in one_page_per_section(mp.site):
        mp.goto_page(section, page)
        assert mp.current() == {"section": section, "page": page}
    mp.reset()
    mp.goto_page(mp.site["sections"][2]["id"], mp.site["sections"][2]["pages"][5]["id"])   # works again after a reset


def test_event_vocabulary_is_identical_across_menus(mp):
    s = mp.site["sections"]
    mp.goto_page(s[0]["id"], s[0]["pages"][0]["id"])
    mp.goto_page(s[1]["id"], s[1]["pages"][2]["id"])
    mp.goto_page(s[0]["id"], s[0]["pages"][0]["id"])               # back to a visited page: a backtrack
    names = set(mp.names())
    assert REQUIRED <= names, (mp.menu_id, REQUIRED - names)
    unexpected = {n for n in names if n not in ALLOWED and not n.startswith("sabotage_")}
    assert not unexpected, (mp.menu_id, unexpected)
    assert ("search_query" in names) == (mp.menu_id == "M6")


def test_backtrack_means_a_visited_location_and_resets_per_task(mp):
    s = mp.site["sections"]
    a, b = (s[0]["id"], s[0]["pages"][1]["id"]), (s[3]["id"], s[3]["pages"][4]["id"])
    mp.goto_page(*a)
    mp.goto_page(*b)
    assert "backtrack" not in mp.names(clear=True)
    mp.goto_page(*a)
    assert mp.names(clear=True).count("backtrack") == 1
    mp.page.click('[data-aoi="nav:home"]')                          # the task starts on home, so returning is a backtrack
    mp.page.wait_for_timeout(200)
    assert "backtrack" in mp.names(clear=True)
    mp.reset()
    mp.goto_page(*a)
    assert "backtrack" not in mp.names()


def test_home_control_and_item_rectangles_are_always_exposed(mp):
    assert "nav:home" in mp.aoi_ids()
    section, page = mp.site["sections"][1]["id"], mp.site["sections"][1]["pages"][3]["id"]
    for action in mp.page.evaluate("([s, p]) => SiteEngine.plan(s, p)", [section, page])[:-1]:
        mp.do(action)
    mp.page.wait_for_timeout(350)
    assert f"item:{section}/{page}" in mp.aoi_ids()                  # the target is on screen right before the last step
    snap = [r for r in mp.page.evaluate("window.__aoi || []") if r["kind"] == "menu"]
    assert snap and any(f"item:{section}/{page}" == r["id"] for s in snap for r in s["rects"]), "AOI snapshot not logged"
    for r in mp.page.evaluate("SiteEngine.menuRects()"):
        assert r["x1"] > r["x0"] and r["y1"] > r["y0"]


def test_every_menu_item_is_at_least_40px_tall_unless_it_is_the_design_idea(mp):
    """Minimum target size (MENUS.md). M3 cards and M4 items are larger by design; M8 wedges are not rectangles."""
    if mp.menu_id == "M8":
        pytest.skip("radial wedges are not boxes")
    section, page = mp.site["sections"][0]["id"], mp.site["sections"][0]["pages"][0]["id"]
    for action in mp.page.evaluate("([s, p]) => SiteEngine.plan(s, p)", [section, page])[:-1]:
        mp.do(action)
    mp.page.wait_for_timeout(350)
    small = [r["id"] for r in mp.page.evaluate("SiteEngine.menuRects()")
             if r["y1"] - r["y0"] < 39.5 and r["id"] != "nav:search"]
    assert not small, (mp.menu_id, small)


# ------------------------------------------------------------------------------------ faults
def sabotage(mp, **probs):
    cfg = {"lag_prob": 0, "lag_min_ms": 400, "lag_max_ms": 500, "drop_click_prob": 0, "menu_glitch_prob": 0,
           "answer_expire_prob": 0, **probs}
    mp.page.evaluate("(c) => SiteEngine.configure({sabotage: c})", cfg)


def test_a_dropped_click_is_silently_ignored_in_every_menu(mp):
    sabotage(mp, drop_click_prob=1)
    section, page = mp.site["sections"][0]["id"], mp.site["sections"][0]["pages"][2]["id"]
    for action in mp.page.evaluate("([s, p]) => SiteEngine.plan(s, p)", [section, page]):
        mp.do(action)
    mp.page.wait_for_timeout(300)
    assert mp.current() is None, "the committing click should have been ignored"
    assert "sabotage_click_dropped" in mp.names()
    assert "page_view" not in mp.names()
    sabotage(mp)                                                   # faults off: the same click now works
    mp.goto_page(section, page)
    assert mp.current() == {"section": section, "page": page}


def test_the_menu_collapses_by_itself_in_every_menu(mp):
    sabotage(mp, menu_glitch_prob=1)
    section, page = mp.site["sections"][2]["id"], mp.site["sections"][2]["pages"][1]["id"]
    for action in mp.page.evaluate("([s, p]) => SiteEngine.plan(s, p)", [section, page])[:-1]:
        mp.do(action)
    mp.page.wait_for_function("SiteEngine.menuState().open === null", timeout=3000)
    names = mp.names()
    assert names.index("menu_open") < names.index("sabotage_menu_glitch"), "the menu must be expanded before it glitches"
    closes = [e for e in mp.events() if e["event"] == "menu_close"]
    assert closes and closes[-1]["detail"]["reason"] == "glitch"


def test_a_slow_page_load_delays_the_page_in_every_menu(mp):
    sabotage(mp, lag_prob=1)
    section, page = mp.site["sections"][4]["id"], mp.site["sections"][4]["pages"][0]["id"]
    for action in mp.page.evaluate("([s, p]) => SiteEngine.plan(s, p)", [section, page]):
        mp.do(action)
    assert mp.current() is None, "the page must not appear before the lag has passed"
    assert "sabotage_lag" in mp.names()
    mp.page.wait_for_function("SiteEngine.menuState().current !== null", timeout=3000)


def test_one_glitch_per_navigation_attempt_not_per_open(mp):
    """Equal fault frequency: a participant who opens the menu several times is glitched once, not every time."""
    sabotage(mp, menu_glitch_prob=1)
    section, page = mp.site["sections"][0]["id"], mp.site["sections"][0]["pages"][0]["id"]
    for action in mp.page.evaluate("([s, p]) => SiteEngine.plan(s, p)", [section, page])[:-1]:
        mp.do(action)
    mp.page.wait_for_function("SiteEngine.menuState().open === null", timeout=3000)
    sabotage(mp, menu_glitch_prob=0)
    before = mp.names().count("sabotage_menu_glitch")
    mp.goto_page(section, page)                                    # the second try works and is not glitched again
    assert mp.names().count("sabotage_menu_glitch") == before == 1


# ------------------------------------------------------------------------------------ static
def test_no_menu_plugin_contains_fault_logic():
    """Faults live in the engine only (prompt section 3)."""
    offenders = []
    for js in (paths.WEB / "core" / "menus").glob("*.js"):
        text = js.read_text(encoding="utf-8")
        if re.search(r"sabotage|Math\.random|drop_click|menu_glitch|lag_prob|sleep\(", text):
            offenders.append(js.name)
    assert not offenders, offenders


def test_every_menu_type_has_a_plugin_and_a_model():
    from hci import menus
    for mid, m in CFG.menus.items():
        assert (paths.WEB / "core" / "menus" / f"{m['type']}.js").exists(), mid
        assert m["type"] in menus.MODELS, mid


# ------------------------------------------------------------------------------ the click models, checked against the menus
def clicks_for(page_obj, section, page):
    page_obj.events(clear=True)
    page_obj.goto_page(section, page)
    return page_obj.names().count("click")


@pytest.mark.parametrize("group,menu_id,second_page_clicks", [
    ("G1", "M2", 1), ("G3", "M9", 1),                       # persistent: the section stays open
    ("G1", "M1", 1), ("G1", "M3", 2), ("G2", "M4", 2), ("G2", "M5", 1), ("G3", "M7", 3), ("G3", "M8", 2),   # not persistent
], ids=lambda v: str(v))
def test_a_second_page_in_the_same_section_costs_what_the_model_says(browser, base_url, group, menu_id, second_page_clicks):
    from hci import menus
    mp = MenuPage(browser, base_url, group, menu_id)
    try:
        sec = mp.site["sections"][3]
        first = clicks_for(mp, sec["id"], sec["pages"][0]["id"])
        second = clicks_for(mp, sec["id"], sec["pages"][4]["id"])
        assert second == second_page_clicks, (menu_id, first, second)
        model = menus.shortest(CFG.menu(menu_id)["type"], [f"{sec['id']}/{sec['pages'][0]['id']}", f"{sec['id']}/{sec['pages'][4]['id']}"])
        assert first + second == model[0], (menu_id, first, second, model)
    finally:
        mp.close()


def test_m6_enter_takes_the_first_suggestion_with_a_single_click(browser, base_url):
    mp = MenuPage(browser, base_url, "G2", "M6")
    try:
        sec = mp.site["sections"][1]
        title = sec["pages"][2]["title"]
        mp.events(clear=True)
        mp.do({"do": "click", "aoi": "nav:search"})
        mp.do({"do": "type", "text": title, "wait": 400})
        mp.do({"do": "key", "key": "Enter", "wait": 300})
        assert mp.current() == {"section": sec["id"], "page": sec["pages"][2]["id"]}
        names = mp.names()
        assert names.count("click") == 1 and "search_query" in names
        query = next(e for e in mp.events() if e["event"] == "search_query")
        assert query["detail"]["query"] == title and query["detail"]["n_results"] >= 1
    finally:
        mp.close()


def test_m6_browse_fallback_takes_three_clicks_and_an_unknown_query_points_to_browse(browser, base_url):
    mp = MenuPage(browser, base_url, "G2", "M6")
    try:
        mp.do({"do": "click", "aoi": "nav:search"})
        mp.do({"do": "type", "text": "zzzz", "wait": 300})
        assert "Try Browse" in mp.page.inner_text(".suggest")
        mp.reset()
        sec = mp.site["sections"][4]
        mp.events(clear=True)
        for aoi in ("nav:browse", f"nav:{sec['id']}", f"item:{sec['id']}/{sec['pages'][1]['id']}"):
            mp.do({"do": "click", "aoi": aoi, "wait": 250})
        assert mp.current() == {"section": sec["id"], "page": sec["pages"][1]["id"]}
        assert mp.names().count("click") == 3
    finally:
        mp.close()
