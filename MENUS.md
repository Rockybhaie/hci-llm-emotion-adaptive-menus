# The nine menus

Three menus per group. A menu belongs to exactly one group (menus are *nested* within groups), so G1 never uses
M4–M9. All nine navigate the same information architecture: **6 sections × 6 pages = 36 pages per site**, and the
page content is identical in every menu. Only the way of navigating changes.

| Group | ID | Menu | Items hidden? | Input | Fastest path |
|---|---|---|---|---|---|
| G1 portal | **M1** | Hover drop-down (the phase-1 menu, unchanged) | yes | hover (or click) | 1 click, 2 steps |
| | **M2** | Persistent sidebar tree | sections visible, pages hidden | click | 1–2 clicks |
| | **M3** | Hub and spoke | yes | click | 2 clicks |
| G2 store | **M4** | Click drop-down with large targets | yes | click | 2 clicks |
| | **M5** | Mega-menu | yes (all sections at once) | click | 2 clicks |
| | **M6** | Search-first | yes (search or browse) | typing | 1 click + typing, 3 steps |
| G3 forum | **M7** | Hamburger drawer | yes | click | 3 clicks |
| | **M8** | Radial (pie) menu | yes | hover + click | 2 clicks, 3 steps |
| | **M9** | Always-visible two-row tab bar | **no** | click | 1–2 clicks |

Configuration lives in [config/menus.yaml](config/menus.yaml) (names, participant-facing labels, parameters) and
[config/groups.yaml](config/groups.yaml) (`menus:` per group). Preview any of them without recording anything:

```powershell
python run.py preview --group G2 --menu M5      # opens the store with the mega-menu (add --debug for a box listing the logged events)
python run.py preview --group G3 --menu M8
```

## Definitions used throughout

- **Click**: a pointer click on a menu control (including the Browse button and the search box).
- **Step**: any discrete action: a click, a hover that opens something, a key press, or typing a query.
  `shortest_clicks` and `shortest_steps` in `tasks.csv` are the fewest clicks / steps the menu needs to visit a
  task's target page(s) *from the home page with the menu at rest*, in whichever order is cheaper. They come from the
  click models in [hci/menus.py](hci/menus.py), which are checked against the real menus (`tests/test_subsets_browser.py`).
- **Persistent menus** (M2, M9) keep the last section open after a page is chosen, so a second page in the same
  section costs one click less. Every task starts with the menu at rest, so this only matters inside a compare task.
- **Backtrack**: a navigation (to a page, or to Home) to a location **already visited earlier in the same task**.
  Home counts as visited, because every task starts on the home page. The visit history is cleared at the start of
  each task. Logged as a `backtrack` event right after the `page_view` / `home_view`, and counted in `tasks.csv`.
  There is no browser Back button in this study (Alt+← is blocked), so browser-Back is not a source of backtracks.
- **Minimum target size**: every menu item is at least **40 px tall** (M1's list items are 41 px). Designs that are larger
  by intent say so below. The test `test_every_menu_item_is_at_least_40px_tall…` enforces this.
- **Item rectangles**: every item carries `data-aoi="nav:<id>"` or `data-aoi="item:<section>/<page>"` and its
  on-screen rectangle is written to `aoi.csv` (kind `menu`) whenever the layout changes (opening, closing, animation
  settling, resizing). Hidden items have no rectangle, so a snapshot is exactly "what could be pointed at right now".

## Events (identical in every menu)

| Event | When |
|---|---|
| `menu_open` / `menu_close` | The menu goes from at-rest to expanded, and back. `detail.state` is `open:<section or panel>` / `closed`; `detail.reason` says why it closed (`select`, `escape`, `outside`, `leave`, `toggle`, `close`, `reset`, `glitch`, `switch`). Moving to another section closes then opens. |
| `item_hover_enter` / `item_hover_exit` | The pointer enters / leaves any menu item (`item` = its id; exit carries `detail.dwell_ms`). |
| `item_select` | Any menu item is chosen (`detail.level` = section, page, home or control; `detail.via` = click or enter). |
| `search_query` | **M6 only**: the query after a short typing pause (`detail.query`, `n_results`). |
| `page_view` / `home_view` | The page that was chosen is now showing (after any induced lag). |
| `backtrack` | See the definition above. |

Panels are named `mega` (M5), `drawer` (M7), `radial` (M8), `search` and `browse` (M6); in the other menus the panel is the
section id. Plus the engine-level events shared by every menu: `click`, `scroll`, `sabotage_*`, `click_while_loading`.

## Induced faults (menu-independent)

Faults are implemented **once**, in [web/core/engine.js](web/core/engine.js); no menu contains fault logic (a test greps
the plug-ins for it). Every sub-block of an emotion block applies the same manipulations to every menu. For the
frustration block the engine rolls once per *navigation attempt*, so a three-step menu is not faulted more often than a
one-step menu:

| Fault | Rule (frustration block) | What it does in each menu |
|---|---|---|
| **Page lag** | probability 0.6 per committing click; 2–6 s | the page does not change for that long; a spinner shows |
| **Ignored click** | probability 0.25 per *committing* click (the click that would choose a page or Home); retries are re-rolled | the click does nothing and is logged as `sabotage_click_dropped` |
| **Menu closes unexpectedly** | probability 0.2 per navigation attempt, 0.5–1.2 s after the menu is first expanded | M1/M4/M5: the open list/panel closes · M2: the tree collapses · M3: the hub closes · M6: the suggestion/browse list disappears (typed text stays) · M7: the drawer closes · M8: the radial menu dismisses · M9: the second row empties and no section stays selected |

("Session expired" on Submit lives in the task bar, outside the menu.) In phase 1 the ignored-click roll was also
applied to section clicks; it now applies only to the committing click so that every menu is faulted equally.

---

## M1 · Hover drop-down (G1)
**Idea:** the baseline. Items are hidden, two steps.
**How:** point at a section in the top bar (opens after a 150 ms intent delay) or click it; a list of its six pages opens;
click one. Closes 400 ms after the pointer leaves, on Escape, outside click or selection.
**Clicks to any page:** 1 (hover then click) · fastest-path steps: 2 · click-to-open: 2.
**Parameters:** `hover_open_ms: 150`, `leave_close_ms: 400`. List items are 41 px tall, 236 px wide.

## M2 · Persistent sidebar tree (G1)
**Idea:** low memory load; all six sections are always visible on the left; no hover needed.
**How:** click a section to unfold its pages (one section open at a time), click a page. The unfolded section stays
unfolded and the current page is highlighted. The sidebar is 272 px wide, so page content is a little narrower
(the content itself is unchanged).
**Clicks to any page:** 2 from rest; 1 if the page's section is already unfolded.
**Parameters:** `accordion: true`. Items are 40–44 px tall.

## M3 · Hub and spoke (G1)
**Idea:** two steps with big, forgiving targets.
**How:** click one of six section tabs; a hub of six large cards (one per page, icon + title) opens over the content;
click a card. The hub stays open until a card is chosen, another tab is clicked, or the participant clicks away.
**Clicks to any page:** always 2.
**Larger targets by design:** cards are at least 299 × 96 px (tabs 48 px tall). The hub is an overlay, so the page underneath is kept.

## M4 · Click drop-down with large targets (G2)
**Idea:** same family as M1, different interaction cost: no hover, stays open, bigger targets.
**How:** click a section; its list opens and stays open until a page is chosen or the participant clicks away
(Escape also closes). Clicking another section switches. Hovering does nothing.
**Clicks to any page:** always 2.
**Larger targets by design:** list items 56 px tall, panel 340 px wide (`item_height_px: 56`).

## M5 · Mega-menu (G2)
**Idea:** see everything at once: no section choice, no hover.
**How:** the bar holds only Home and one **All pages** button. Click it; a full-width panel opens showing all six
sections side by side as headed columns, each with its six pages (36 pages in view). Click a page. Closes on
selection, Escape, a second click on the button or an outside click. Hovering does nothing.
**Clicks to any page:** always 2 (open the panel, click the page) · steps: 2.
**Parameters:** none; items are 41 px tall. *Distinct from M1 and M4:* they reveal one section at a time after a choice
among sections; M5 has no section step, trading one click for a wider scan.

## M6 · Search-first (G2)
**Idea:** typing instead of pointing.
**How:** a search box over all 36 page titles, and a Browse button as the fallback.
*Search*: click the box, type part of a page title, then press Enter (takes the first suggestion) or click a suggestion
(up to 7, each showing its section). Matching is on **page titles only**, case-insensitive: exact title first, then titles
starting with the query, then words starting with it, then any substring. Arrow keys move through suggestions.
*Browse*: click Browse, click a section to unfold its pages, click the page.
**Clicks to any page:** search: 1 click + typing (Enter) or 2 clicks (suggestion) · browse: 3 clicks. Steps: 3.
**Parameters:** `max_results: 7`, `debounce_ms: 250` (for `search_query`). The search box is 42 px tall; results 44 px.
Note that tasks name an *item* (for example "Burr Coffee Grinder"), not its page ("Coffee & Tea"), so participants must
first work out which page to search for, as in every other menu.

## M7 · Hamburger drawer (G3)
**Idea:** hidden, mobile-style, with drill-down screens.
**How:** press the menu button (three lines) at the top left; a wide drawer (up to 560 px) slides in over a dimmed page
and lists only the six sections. Press a section: the drawer **replaces** the list with that section's pages and a Back
button; press a page. Closing the drawer returns it to the section list, so there is no history dependence. Home is
always visible next to the button.
**Clicks to any page:** always 3. (Back is an extra click only if the participant picked the wrong section.)
**Parameters:** `drill_down: true`. Rows are 52 px on the page screen. *Distinct from M2:* the sidebar tree is always
on screen and unfolds pages in place; the drawer is hidden and moves between two screens.

## M8 · Radial (pie) menu (G3)
**Idea:** spatial, gesture-like; sectors and pages are always at the same angles.
**How:** press the round Menu button; a circle of six sector wedges opens in the middle of the page over a dimmed
background. Moving onto a sector (after 90 ms) or clicking it fans its six pages out into an outer ring; click a page.
The centre is a Close button. Home is always visible next to the button.
**Clicks to any page:** 2 (open, page) with hover-reveal · 3 if sectors are clicked · steps: 3.
**Parameters:** `inner_radius_px: 70`, `mid_radius_px: 150`, `outer_radius_px: 235`. Wedges are not rectangles; each
wedge's bounding box is logged (measured at a 1600 × 900 window: every wedge is at least 168 × 108 px). The ring is sized
from the window height, so it shrinks in a small window.

## M9 · Always-visible two-row tab bar (G3)
**Idea:** everything visible, no hidden state, nothing opens.
**How:** row 1 shows the six sections, row 2 the six pages of the selected section (an empty prompt when none is
selected). Click a section, then a page. The section stays selected after a page is chosen; the current section and page
are highlighted.
**Clicks to any page:** 2 from rest; 1 if the section is already selected.
**Parameters:** none. Items are 42–48 px tall.

---

## Summary of costs (computed from the models, verified in the real menus)

| Menu | Fastest path, clicks (min–max over states) | Steps | Typical use |
|---|---|---|---|
| M1 | 1–1 | 2 | hover, click |
| M2 | 1–2 | 1–2 | click, click |
| M3 | 2–2 | 2 | click, click |
| M4 | 2–2 | 2 | click, click |
| M5 | 2–2 | 2 | click, click |
| M6 | 1–1 (Enter) or 2 (suggestion) | 3 | click box, type, Enter/click |
| M7 | 3–3 | 3 | click, click, click |
| M8 | 2–2 | 3 | click, hover, click |
| M9 | 1–2 | 1–2 | click, click |

Total fastest clicks for the 4 tasks of one subset (six subsets): M1 5·5·5·5·5·5 · M2 10·10·10·9·10·9 · M3 10 every subset ·
M4 10 · M5 10 · M6 5 · M7 15 · M8 10 · M9 9·9·10·9·10·9. Within a menu the six subsets cost about the same, so a subset can be paired with any menu.

## Adding or changing a menu

A menu is one JavaScript module in [web/core/menus/](web/core/menus/) plus an entry in [config/menus.yaml](config/menus.yaml)
and a click model in [hci/menus.py](hci/menus.py). The contract is documented at the top of
[web/core/menus/registry.js](web/core/menus/registry.js): register every interactive element with `api.item()`, report expansion
only through `api.setOpen()`, provide `collapse()`, `reset()` and `plan()`, and keep a Home control visible. Then run
`python -m pytest tests/test_menus_browser.py tests/test_subsets_browser.py`.
