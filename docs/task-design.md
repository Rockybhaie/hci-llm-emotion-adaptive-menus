# Websites and tasks

## The three websites

All three are our own builds on one shared engine (`web/core/`), so menu behaviour, timing and logging are identical. Only the content and visual theme differ. Each site's information architecture is modelled on a WebArena site (Zhou et al., *WebArena: A Realistic Web Environment for Building Autonomous Agents*, ICLR 2024): a realistic, published environment, rebuilt in a light form we can control and instrument.

| Group | Site | Modelled on | Page layout |
|---|---|---|---|
| G1 | Northfield University student portal | WebArena content-management admin panel | Tables (courses, fees, services …) |
| G2 | Everyday Market store | WebArena *OneStopShop* | Product cards (price, rating, item code, stock) |
| G3 | Threadline forum | WebArena *Postmill* (Reddit-style) | Thread lists (votes, replies, author, flair) |

The structure is identical across the three sites: **6 sections × 6 pages = 36 pages**, plus a home page. Each page holds 5–6 items. The content is in `web/sites/<site>/site.json`. **The page content is the same in every menu**; only the way of reaching a page changes ([MENUS.md](../MENUS.md)).

**A menu is the only way to navigate.** The breadcrumb is plain text, there is no site search (except M6, whose search box *is* the menu) and page content has no links, so every navigation in the data is a menu interaction. Each group uses three menus; the menus are described, with their costs and the events they log, in [MENUS.md](../MENUS.md).

## Task subsets: S1–S6 and the practice pool P

Each group's task file ([config/tasks/](../config/tasks/)) has **six subsets of four tasks** (one per emotion × menu cell) and a **practice pool** of six tasks. Every subset has the same four tasks in the same order:

| Position | Type | Example (G2) | What it measures |
|---|---|---|---|
| 1 | **lookup**: find a named item, read one field | "Find the Trailblazer 2-Person Tent. What is its price?" | Locating the right section from the item name alone |
| 2 | **extreme**: on one page, find the item with the max or min value | "Find the cheapest vitamin or supplement in the store." | Navigation plus scanning a page |
| 3 | **lookup** (a different page and, where possible, a different field) | "Find the Aurora ANC Over-Ear Headphones." | |
| 4 | **compare**: two items on two **different** pages | "Which is cheaper: the Yoga Mat 6 mm or the Vitamin C Serum?" | Multi-page navigation and working memory |

The subsets are **type-matched** (identical mix and order) and **difficulty-matched**: every target page is two levels deep in every menu, each subset has five target pages (one for each lookup and the extreme, two for the compare), and the fewest clicks a menu needs for the subset is almost the same for all six (for example M2: 10, 10, 10, 9, 10, 9; see [MENUS.md](../MENUS.md#summary-of-costs-computed-from-the-models-verified-in-the-real-menus)). `tests/test_core.py` enforces the type mix, two-page compares, a spread of at most four clicks per menu, and the 8 % margin rule below.

- **Within a group, a subset works with any of the group's three menus.** `tests/test_subsets_browser.py` completes every task of every subset in each of the three real menus and checks the click counts against the model.
- Answers and the multiple-choice options (the correct value plus 3 distractors from the same page, then the rest of the site) are **computed from `site.json` at start-up**. Editing the content can never leave a stale answer, and the browser never receives the correct answer.
- "Extreme" and "compare" answers always differ from the runner-up by at least 8 %, so no answer hinges on a near-tie. A compare item may name its own `field`, so a fee on one page can be compared with a deposit on another (used in G1, where each page has different columns).
- **Boredom variant:** in the boredom block every task becomes the same template on the same target pages ("Find *X* in *Y*. What is its item code?"); task ids get an `R` suffix.

### How the subsets were built from the 24 phase-1 tasks per site

Phase 1 had two sets of 12 tasks per site (16 lookup, 4 extreme, 4 compare). Equal subsets of four need 12 lookups, 6 extremes and 6 two-page compares, so tasks were reused where they fitted and new ones written to fill the gaps. The assignment was chosen by a small search that prefers existing tasks, avoids repeating a target page, and spreads sections evenly.

| | Reused from phase 1 | New experimental tasks | Practice pool (6 each) |
|---|---|---|---|
| G1 portal | 12 lookups, 4 extremes, 2 compares | **6**: 2 extremes (grades weighting, event capacity), 4 two-page money compares | 1 reused (`A08`, HCI final), 5 new |
| G2 store | 12 lookups, 4 extremes, 4 compares | **4**: 2 extremes (lowest-rated watch/jewellery, most expensive phone/tablet), 2 compares | 1 reused (`A01`, the tent), 5 new |
| G3 forum | 12 lookups, 4 extremes, 4 compares | **4**: 2 extremes (Europe votes, vegetarian replies), 2 compares | 2 reused (`A06`, `A10`), 4 new |
| **Total** | | **14 experimental tasks** | **14 new practice tasks** (28 new in all) |

Four of the 16 phase-1 lookups per site were not needed in the subsets (G1 `A02 A06 A08 B02`, G2 `A01 A03 A09 B09`, G3 `A06 A10 B02 B03`); some became practice tasks. G1's two phase-1 "compare" tasks that compared two items on the *same* page (`A12`, `B12`) were dropped, because a one-page compare is easier than a two-page one. All new tasks are in the same style as the old ones, and their answers are computed from the site content like every other task.

The target pages of the 30 task slots (6 subsets × 5 pages) are 30 distinct pages in G3, 28 in G2 (two pages appear twice) and 22 in G1. G1 has the most repeats because only a handful of its pages have comparable money values, so the Transcripts and Finance pages recur as compare targets.

### Practice pool

Six simple lookups per site on pages **no subset targets** (checked by a test), so practising a menu cannot pre-teach a target page. Menu *i* of the group practises on `P[2i]` and `P[2i+1]` (in different sections). Practice has no time pressure (a 120 s cap only prevents getting stuck), no induced manipulation, a neutral "Answer saved" message, and its rows have `phase = practice`.

## How a sub-block works

- **Exactly 4 tasks**, in order, with a **per-task limit** of 40 s (`timings.task_timeout`; 30 s with a visible countdown in the stress block, `in_task.timeout`). A sub-block therefore takes at most about 2.7 min (2 min under stress). There is no block timer.
- Each task starts on the home page with the menu closed and the visit history empty.
- The participant clicks **Answer**, picks one option and submits. One answer per task.
- The first sub-block of an emotion block shows the full instructions and the menu's description; the next two show a short "the menu changes" card with the new menu's description.
- Outcomes: `correct`, `incorrect`, `timeout`, `not_reached` (only if a session is cut short), `abandoned`/`aborted` (interrupted).

## Measures per task (`tasks.csv`)

| Measure | Meaning |
|---|---|
| `correct`, `outcome` | 1/0 and the outcome |
| `duration_s` | Time from task start to answer |
| `clicks`, `menu_clicks` | All clicks inside the site; those on menu items |
| `menu_opens` | Number of `menu_open` events |
| `page_views`, `wrong_pages` | Pages visited; pages visited that are not a target (a classic navigation-error measure) |
| `backtracks` | Navigations to a location already visited in this task (home counts; see [MENUS.md](../MENUS.md#definitions-used-throughout)) |
| `shortest_clicks`, `shortest_steps` | Fewest clicks / discrete steps this menu needs to visit the target page(s) from home |
| `mouse_path_px` | Length of the mouse path during the task, in screen pixels (from the sampled positions) |
| `sabotage_events`, `answer_attempts` | Frustration manipulations that hit this task; submissions including ones rejected as "session expired" |

`excess_menu_clicks` in `subblocks.csv` is `menu_clicks − shortest_clicks` summed over the sub-block (it can be below zero for hover menus, where the shortest path counts the hover as no click).

The fine-grained stream (`events.csv`, `mouse.csv`, `aoi.csv`) also allows hover dwell per menu item (`item_hover_enter`/`exit`, `detail.dwell_ms`), hesitation before selection, mouse speed and jitter (Hibbeln et al., 2017), and, once sensors are added, gaze-on-menu time.
