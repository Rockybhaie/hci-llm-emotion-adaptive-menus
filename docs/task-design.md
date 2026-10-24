# Websites and tasks

## The three websites

All three are our own builds on one shared engine (`web/core/`), so menu behaviour, timing and logging are identical. Only the content and visual theme differ. Each site's information architecture is modelled on a WebArena site (Zhou et al., *WebArena: A Realistic Web Environment for Building Autonomous Agents*, ICLR 2024): a realistic, published environment, rebuilt in a light form we can control and instrument.

| Group | Site | Modelled on | Page layout |
|---|---|---|---|
| G1 | Northfield University student portal | WebArena content-management admin panel | Tables (courses, fees, services …) |
| G2 | Everyday Market store | WebArena *OneStopShop* | Product cards (price, rating, item code, stock) |
| G3 | Threadline forum | WebArena *Postmill* (Reddit-style) | Thread lists (votes, replies, author, flair) |

The structure is identical across the three sites: **6 sections × 6 pages = 36 pages**, plus a home page. Each page holds 5–6 items. The content is in `web/sites/<site>/site.json`, which you can edit directly.

**The standard drop-down menu is the only way to navigate.** The breadcrumb is plain text, there is no search, and page content has no links. Every navigation in the data is therefore a menu interaction, which is exactly what phase 2 will adapt. The menu opens on hover (150 ms intent delay) or click, and closes on mouse-leave (400 ms grace), Escape, a click outside it, or a selection. All of these are logged.

## Task types

Each group has two **parallel task sets (A and B)** of 12 tasks, in [config/tasks/](../config/tasks/). The two sets are matched on every dimension:

| Position | Type | Example (G2) | What it measures |
|---|---|---|---|
| 1–4, 6–7, 9–10 | **lookup**: find a named item, read one field | "Find the Trailblazer 2-Person Tent. What is its price?" | Locating the right section from the item name alone |
| 5, 8 | **extreme**: on one page, find the item with the max or min value | "Find the cheapest vitamin or supplement." | Navigation plus scanning a page |
| 11–12 | **compare**: two items on (usually) different pages | "Which is cheaper: the Yoga Mat or the Vitamin C Serum?" | Multi-page navigation and working memory |

- Both sets visit every section twice and use the same field types in the same positions.
- "Extreme" and "compare" answers always differ from the runner-up by at least 8%, so no answer hinges on a near-tie. An automated test enforces this.
- Answers and the multiple-choice options (the correct value plus 3 distractors from the same page, then the rest of the site) are **computed from site.json at start-up**. Editing the content can never leave a stale answer. The browser never receives the correct answer.
- **Boredom variant:** in the boredom block, every task becomes the same template on the same targets ("Find *X* in *Y*. What is its item code?").

## How a task block works

- Fixed **6-minute** blocks, so every emotion contributes the same amount of data per person. Tasks run in order. Any not started when time runs out are logged as `not_reached`.
- Each task starts on the home page with the menu closed.
- The participant clicks **Answer**, picks one option and submits. One answer per task.
- Time limit per task: 90 s (60 s with a visible countdown in the stress block).
- Outcomes: `correct`, `incorrect`, `timeout` (task limit), `time_up` (block ended mid-task), `not_reached`.

## Measures per task (`tasks.csv`)

| Measure | Meaning |
|---|---|
| `duration_s` | Time from task start to answer |
| `clicks` | All clicks inside the site during the task |
| `menu_opens` | Number of drop-down openings |
| `page_views` / `wrong_pages` | Pages visited / pages visited that are not a target, a classic navigation-error measure |
| `sabotage_events` | Frustration manipulations that hit this task |
| `answer_attempts` | Submissions, including ones rejected as "session expired" |

The fine-grained stream (`events.csv`, `mouse.csv`, `aoi.csv`) also allows hover dwell per menu item, hesitation before selection, mouse speed and jitter (Hibbeln et al., 2017), and gaze-on-menu time.
