"""Shared helpers for tests that drive the real menus in Microsoft Edge (via Playwright).

The tests skip themselves when Playwright or Edge is not installed.
"""

import socket

from hci import config

try:
    from playwright.sync_api import sync_playwright
except ImportError:                      # pragma: no cover
    sync_playwright = None

SITE_OF_GROUP = {"G1": "g1-portal", "G2": "g2-store", "G3": "g3-forum"}


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class MenuPage:
    """One site + menu loaded in a page, with helpers to walk it like a person would."""

    def __init__(self, browser, base_url, group, menu_id, viewport=(1280, 800)):
        self.cfg = config.load()
        self.group, self.menu_id = group, menu_id
        self.site = config.load_site(SITE_OF_GROUP[group])
        self.page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
        self.page.goto(f"{base_url}/core/site.html?site={SITE_OF_GROUP[group]}&menu={menu_id}&record=1")
        self.page.evaluate("SiteEngine.ready")
        self.page.wait_for_selector("main .crumbs")

    # -- driving ----------------------------------------------------------------------------
    def center(self, aoi):
        box = self.page.evaluate(
            "(id) => { const e = document.querySelector(`[data-aoi=\"${id}\"]`); if (!e) return null;"
            " const r = e.getBoundingClientRect(); return r.width && r.height ? [r.left + r.width/2, r.top + r.height/2] : null; }",
            aoi)
        return box

    def do(self, action):
        kind = action["do"]
        if kind in ("hover", "click"):
            xy = self.center(action["aoi"])
            assert xy, f"{self.menu_id}: '{action['aoi']}' is not visible for action {action}"
            if kind == "hover":
                self.page.mouse.move(2, 640)                 # leave first: a hover is an entry (mouseenter)
            self.page.mouse.move(*xy)
            if kind == "click":
                self.page.mouse.click(*xy)
        elif kind == "type":
            self.page.keyboard.type(action["text"], delay=15)
        elif kind == "key":
            self.page.keyboard.press(action["key"])
        self.page.wait_for_timeout(action.get("wait", 120))

    def goto_page(self, section, page):
        for action in self.page.evaluate("([s, p]) => SiteEngine.plan(s, p)", [section, page]):
            self.do(action)
        self.page.wait_for_function(
            "([s, p]) => { const c = SiteEngine.menuState().current; return c && c.section === s && c.page === p; }",
            arg=[section, page], timeout=4000)

    def reset(self):
        self.page.evaluate("SiteEngine.reset()")
        self.page.mouse.move(5, 400)
        self.page.wait_for_timeout(80)

    def events(self, clear=False):
        ev = self.page.evaluate("window.__events || []")
        if clear:
            self.page.evaluate("window.__events = []")
        return ev

    def names(self, clear=False):
        return [e["event"] for e in self.events(clear)]

    def aoi_ids(self):
        return {r["id"] for r in self.page.evaluate("SiteEngine.menuRects()")}

    def current(self):
        return self.page.evaluate("SiteEngine.menuState().current")

    def close(self):
        self.page.close()
