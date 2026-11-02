"""Every task of every subset (and the practice pool) can be completed in each of the group's three menus.

For each menu the real plug-in is driven with a mouse through the menu's own plan() to every target page of every
task, starting each task from home with the menu at rest, exactly as a session does. The number of clicks used is
compared with the click model in hci/menus.py (`shortest_clicks` in tasks.csv).
"""

import pytest

from browser_support import MenuPage
from hci import config, counterbalance, tasks

pytestmark = pytest.mark.slow

CFG = config.load()
ALL = [(gid, mid) for gid, g in CFG.groups.items() for mid in g["menus"]]


@pytest.mark.parametrize("group,menu_id", ALL, ids=[f"{g}-{m}" for g, m in ALL])
def test_every_task_is_solvable_and_the_click_model_matches_the_menu(browser, base_url, group, menu_id):
    gcfg = CFG.group(group)
    site = config.load_site(gcfg["site"])
    task_cfg = config.load_tasks(gcfg["tasks"])
    menu_type = CFG.menu(menu_id)["type"]
    mp = MenuPage(browser, base_url, group, menu_id)
    try:
        checked = pages_seen = 0
        for subset in [*counterbalance.SUBSETS, "P"]:
            for task in tasks.build_subset(site, task_cfg, subset, seed=1, menu_type=menu_type):
                mp.reset()
                mp.events(clear=True)
                for target in task["targets"]:
                    mp.goto_page(*target.split("/"))
                    pages_seen += 1
                clicks = mp.names().count("click")
                assert clicks >= task["shortest_clicks"], (menu_id, task["id"], clicks, task["shortest_clicks"])
                if menu_id != "M6":          # M6's plan clicks a suggestion (2 clicks); its model also allows Enter (1 click)
                    assert clicks == task["shortest_clicks"], (menu_id, task["id"], clicks, task["shortest_clicks"])
                checked += 1
        assert checked == 6 * 4 + 6
        assert pages_seen >= 30
    finally:
        mp.close()
