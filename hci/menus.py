"""The nine menus: registry and click-cost models.

Each menu *type* has a small model of how many actions it takes to reach a page. The model is the
written-down rule set of the menu (MENUS.md) in executable form. It is used for

  * `shortest_clicks` / `shortest_steps` in tasks.csv, and
  * the tests that prove every task subset is solvable from every menu.

A menu has a *persistent state*: the section whose pages are currently shown. Hover or click-to-open
menus close on selection (state stays None); the sidebar tree and the two-row tab bar keep the
section open after a page is chosen, so a second page in the same section is one click cheaper.

Definitions
  click : a pointer click on a menu control (including the Browse button and search box).
  step  : any discrete action: a click, a hover that opens something, a key press, or typing a query.
"""

from itertools import permutations
from typing import NamedTuple


class Cost(NamedTuple):
    clicks: int
    steps: int


class Move(NamedTuple):
    cost: Cost
    state: object      # persistent state after reaching the page


# --- one function per menu type: (state, section) -> list of alternative Moves ------------------
# `state` is the section currently expanded in a persistent menu, or None.

def _hover_dropdown(state, section):
    # Hover opens the list (no click), or click-to-open as an alternative; then click the page.
    return [Move(Cost(1, 2), None), Move(Cost(2, 2), None)]


def _click_dropdown(state, section):
    return [Move(Cost(2, 2), None)]


def _mega(state, section):
    # click the single "All pages" button, then click the page in the full-width panel
    return [Move(Cost(2, 2), None)]


def _hub(state, section):
    return [Move(Cost(2, 2), None)]


def _sidebar(state, section):
    if state == section:
        return [Move(Cost(1, 1), section)]
    return [Move(Cost(2, 2), section)]


def _tabs(state, section):
    if state == section:
        return [Move(Cost(1, 1), section)]
    return [Move(Cost(2, 2), section)]


def _search(state, section):
    # focus the box, type, then either click a suggestion (2 clicks) or press Enter (1 click);
    # or Browse > section > page (3 clicks).
    return [Move(Cost(1, 3), None), Move(Cost(2, 3), None), Move(Cost(3, 3), None)]


def _drawer(state, section):
    return [Move(Cost(3, 3), None)]


def _radial(state, section):
    # press the button, move over (or click) a sector, click the page
    return [Move(Cost(2, 3), None), Move(Cost(3, 3), None)]


MODELS = {
    "hover-dropdown": _hover_dropdown,
    "sidebar-tree": _sidebar,
    "hub-spoke": _hub,
    "click-dropdown": _click_dropdown,
    "mega-menu": _mega,
    "search-first": _search,
    "drawer": _drawer,
    "radial": _radial,
    "two-row-tabs": _tabs,
}

# Persistent menus start every task collapsed (the task starts on the home page with the menu closed).
HOME_COST = Cost(1, 1)    # every menu has an always-visible Home control


def reach(menu_type, state, section):
    """Alternatives for reaching a page of `section` while the menu is in `state`."""
    return MODELS[menu_type](state, section)


def _best(menu_type, targets, key):
    """Cheapest total over every visiting order of `targets` ([(section, page), ...])."""
    best = None
    for order in permutations(targets):
        state, total = None, 0
        for section, _ in order:
            move = min(reach(menu_type, state, section), key=lambda m: getattr(m.cost, key))
            total += getattr(move.cost, key)
            state = move.state
        best = total if best is None else min(best, total)
    return best


def shortest(menu_type, targets):
    """(shortest_clicks, shortest_steps) to visit every target page, from the home page, menu closed.

    `targets` are page ids like 'finance/tuition'. The participant may visit them in either order.
    """
    pairs = [tuple(t.split("/", 1)) for t in dict.fromkeys(targets)]
    return _best(menu_type, pairs, "clicks"), _best(menu_type, pairs, "steps")


def click_range(menu_type, sections):
    """(fewest, most) clicks of the *fastest* path to a single page, over every menu state."""
    states = [None, *sections]
    costs = [min(m.cost.clicks for m in reach(menu_type, st, sec)) for st in states for sec in sections]
    return min(costs), max(costs)


def step_range(menu_type, sections):
    states = [None, *sections]
    costs = [min(m.cost.steps for m in reach(menu_type, st, sec)) for st in states for sec in sections]
    return min(costs), max(costs)
