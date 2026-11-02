"""A scripted participant for dry runs: drives the real participant shell in Edge through a whole session.

    python tools/participant_bot.py --group G2 --participant P03            # fast dry run (about 4 min)
    python tools/participant_bot.py --group G1 --participant P01 --real-time # real timings, human-like pauses

It starts the same server the researcher would, opens the shell in a headless Edge (via Playwright) and
answers every screen: consent, demographics, ratings, practice, every task through the menu's own
`plan()` (retrying when an induced fault swallows a click, as a person would), boosters, ranking, debrief.
Data is saved in a throw-away folder (or --data-root). Missing stimulus videos become placeholders (--pilot).

Used by tests/test_dry_run_browser.py and for the duration measurement in the final report.
"""

import argparse
import random
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import TimeoutError as PlaywrightTimeout  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from hci import config  # noqa: E402
from hci.server import ServerThread, create_app  # noqa: E402
from hci.session import Session  # noqa: E402
from tests.browser_support import free_port  # noqa: E402


class Bot:
    def __init__(self, session, page, real_time=False, rng=None, mistakes=0.15):
        self.s, self.page = session, page
        self.real_time = real_time
        self.rng = rng or random.Random(5)
        self.mistakes = mistakes
        self.log = []

    # -- pacing --------------------------------------------------------------------------------
    def pause(self, lo, hi):
        """Human-like thinking time in real-time mode; a tiny pause in a fast dry run."""
        time.sleep(self.rng.uniform(lo, hi) if self.real_time else 0.05)

    def wait_step_done(self, index, timeout=900):
        end = time.time() + timeout
        while time.time() < end:
            if self.s.current > index or self.s.done.is_set():
                return
            time.sleep(0.15)
        raise TimeoutError(f"step {index} ({self.s.steps[index]['type']}) did not finish")

    def settle(self, index, timeout=60):
        """Wait until the shell has started this step and finished swapping screens.

        The shell fades the old screen out for 160 ms before the new one replaces it, so for a moment the previous
        step's buttons (#go) are still in the page. Acting before that would click the stale button.
        """
        end = time.time() + timeout
        while index not in self.s.started and time.time() < end and not self.s.done.is_set():
            time.sleep(0.05)
        time.sleep(0.5)

    def click(self, selector, timeout=60000):
        self.page.wait_for_selector(selector, state="visible", timeout=timeout)
        self.page.click(selector)

    def click_when_enabled(self, selector, timeout=120):
        end = time.time() + timeout
        while time.time() < end:
            if self.page.locator(selector).count() and self.page.locator(selector).first.is_enabled():
                self.page.click(selector)
                return
            time.sleep(0.2)
        raise TimeoutError(selector)

    # -- screens -------------------------------------------------------------------------------
    def welcome(self, step):
        self.pause(3, 6)
        self.click("#go")

    def consent(self, step):
        self.page.wait_for_selector("[data-c]")
        self.pause(15, 30)
        for box in self.page.locator("[data-c]").all():
            box.check()
        self.click("#yes")

    def demographics(self, step):
        self.page.wait_for_selector("#f")
        self.pause(15, 25)
        self.page.fill("input[name=age]", "24")
        for name in ("gender", "handedness", "vision", "computer_hours", "site_familiarity", "caffeine_2h"):
            self.page.locator(f"input[name={name}]").first.check(force=True)
        self.click("#go")

    def rest(self, step):
        self.click("#go")

    def rating(self, step):
        index = step["index"]
        end = time.time() + 120
        while self.s.current == index and time.time() < end:
            rows = self.page.locator(".sam, .likert, .tlx")
            if not rows.count() or not self.page.locator("#go").count():
                time.sleep(0.2)
                continue
            self.pause(2, 5)
            for row in rows.all():
                kind = row.get_attribute("class") or ""
                dots = row.locator(".sam-dot") if "sam" in kind else row.locator(".seg") if "likert" in kind else row.locator(".tick")
                dots.nth(self.rng.randrange(dots.count())).click()
                self.pause(0.5, 1.5)
            self.click_when_enabled("#go")
            time.sleep(0.5)

    def menu_rank(self, step):
        self.page.wait_for_selector(".rank-card")
        self.pause(3, 8)
        cards = self.page.locator(".rank-card")
        order = list(range(cards.count()))
        self.rng.shuffle(order)
        for i in order:
            cards.nth(i).click()
        self.click_when_enabled("#go")

    def induction(self, step):
        kind = step["params"]["kind"]
        if kind in ("mist", "breathing", "copying", "briefing", "film"):
            self.click_when_enabled("#go")
        # the activity itself runs for its configured duration

    def booster(self, step):
        # Boosters advance by themselves. Clicking the frustration booster's Continue would race that auto-advance
        # (in --fast mode both fire after 3 s) and the click could land on the next screen's Begin button.
        pass

    def washout(self, step):
        self.click_when_enabled("#go")

    def debrief(self, step):
        self.page.wait_for_selector("[name=retain]")
        self.pause(10, 20)
        self.page.locator("[name=retain][value=yes]").check(force=True)
        self.click("#go")

    # -- tasks ---------------------------------------------------------------------------------
    def tasks(self, step):
        self.click_when_enabled("#go")                                   # the intro card
        self.page.wait_for_selector("#site")
        frame = self.page.frame_locator("#site")
        site = self.page.frames[-1]
        for _ in range(100):
            if site.evaluate("typeof SiteEngine !== 'undefined'"):
                break
            time.sleep(0.1)
        for n, task in enumerate(step["tasks_full"]):
            if self.s.current != step["index"]:
                return
            try:
                self.one_task(site, step, n, task)
            except (PlaywrightError, PlaywrightTimeout, AssertionError):
                # An induced fault (page lag) can run the shell's per-task time limit out while we are still
                # navigating: the shell has then moved on. A person would simply carry on with the next task.
                if self.s.current != step["index"]:
                    return
                self.log.append((step["index"], f"task {task['id']} abandoned", 0))
        # the shell shows an end card and then completes the step by itself

    def one_task(self, site, step, n, task):
        self.page.wait_for_function(
            "(n) => document.querySelector('#tn') && Number(document.querySelector('#tn').textContent) === n", arg=n + 1,
            timeout=15000)
        self.page.wait_for_function("window.HCI && HCI.ctx.task_id !== ''", timeout=15000)
        self.pause(4, 9)                                              # read the task
        for target in task["targets"]:
            self.reach(site, *target.split("/"))
        self.pause(2, 5)
        if self.s.current != step["index"]:
            return
        self.answer(task, step)

    def reach(self, site, section, page):
        for attempt in range(12):
            if site.evaluate("([s, p]) => { const c = SiteEngine.menuState().current; return !!c && c.section === s && c.page === p; }",
                             [section, page]):
                return
            if self.s.done.is_set():
                return
            for action in site.evaluate("([s, p]) => SiteEngine.plan(s, p)", [section, page]):
                self.act(site, action)
            for _ in range(60):                                          # wait for a slow page (induced lag)
                if site.evaluate("([s, p]) => { const c = SiteEngine.menuState().current; return !!c && c.section === s && c.page === p; }",
                                 [section, page]):
                    return
                time.sleep(0.1)
        raise AssertionError(f"could not reach {section}/{page}")

    def act(self, site, action):
        kind = action["do"]
        loc = site.locator(f'[data-aoi="{action["aoi"]}"]').first if "aoi" in action else None
        if kind == "hover":
            self.page.mouse.move(2, 640)
            loc.hover()
        elif kind == "click":
            loc.click()
        elif kind == "type":
            self.page.keyboard.type(action["text"], delay=40 if self.real_time else 10)
        elif kind == "key":
            self.page.keyboard.press(action["key"])
        time.sleep((action.get("wait", 120) / 1000) * (1.3 if self.real_time else 1))
        self.pause(0.4, 1.0)

    def answer(self, task, step):
        wrong = self.rng.random() < self.mistakes
        choice = next((o for o in task["options"] if o != task["answer"]), task["answer"]) if wrong else task["answer"]
        self.page.click("#answer")
        for attempt in range(4):                                          # an induced "session expired" asks twice
            self.page.locator(".opt", has_text=choice).first.click()
            self.pause(0.5, 1.5)
            self.page.click("#submit")
            time.sleep(0.4)
            if not self.page.locator("#perr").is_visible():
                return
        raise AssertionError("answer was never accepted")

    HANDLERS = {"welcome": welcome, "consent": consent, "demographics": demographics, "rest": rest, "rating": rating,
                "practice": tasks, "tasks": tasks, "induction": induction, "booster": booster, "washout": washout,
                "menu_rank": menu_rank, "debrief": debrief}

    def run(self, deadline_s=7200):
        end = time.time() + deadline_s
        while not self.s.done.is_set() and time.time() < end:
            index = self.s.current
            step = self.s.steps[index]
            if step["type"] == "end":
                break
            handler = self.HANDLERS.get(step["type"])
            if handler is None:
                raise AssertionError(f"no handler for {step['type']}")
            t0 = time.time()
            self.settle(index)
            try:
                handler(self, step)
            except Exception:
                shot = Path(tempfile.gettempdir()) / f"hci-bot-failure-{self.s.group_id}-{self.s.participant}.png"
                try:
                    self.page.screenshot(path=str(shot))
                    visible = " | ".join(self.page.inner_text("body")[:400].splitlines())
                except Exception as exc:
                    visible = f"(page unavailable: {exc})"
                print(f"BOT FAILED in step {index} ({step['type']}), server current={self.s.current}; page shows: {visible}; screenshot {shot}")
                raise
            self.wait_step_done(index)
            self.log.append((index, step["type"], round(time.time() - t0, 1)))
        return self.log


def run_session(group, participant, data_root=None, fast=True, real_time=False, headless=True, seed=5, resume=False,
                stop_at=None):
    """Run one whole session in Edge. Returns (session, log). `stop_at(step)` -> True aborts early (resume tests)."""
    cfg = config.load()
    root = Path(data_root or tempfile.mkdtemp(prefix="hci-dry-"))
    session = Session(cfg, group, participant, fast=fast, pilot=True, resume=resume, data_root=root)
    session._save()
    server = ServerThread(create_app(session), "127.0.0.1", free_port()).start()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=headless,
                                    args=["--autoplay-policy=no-user-gesture-required"])
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        page.goto(server.url)
        bot = Bot(session, page, real_time=real_time, rng=random.Random(seed))
        try:
            log = bot.run()
        finally:
            browser.close()
            time.sleep(0.5)
            server.stop()
    return session, log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", required=True, choices=["G1", "G2", "G3"])
    ap.add_argument("--participant", required=True)
    ap.add_argument("--real-time", action="store_true", help="real timings and human-like pauses (about 50 min)")
    ap.add_argument("--data-root")
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    session, log = run_session(args.group, args.participant, args.data_root, fast=not args.real_time,
                               real_time=args.real_time, headless=not args.headed)
    print(f"{args.group}/{args.participant} finished: status={session.status} in {(time.time() - t0) / 60:.1f} min wall clock; "
          f"session clock {session.snapshot()['elapsed'] / 60:.1f} min; saved to {session.folder}")
    if args.real_time:
        for index, kind, secs in log:
            print(f"  step {index:2d} {kind:12s} {secs:6.1f}s")


if __name__ == "__main__":
    main()
