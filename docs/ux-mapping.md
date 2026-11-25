# UX goals of the menus: from physical input to indicator

This app measures each menu against seven UX goals (Preece, Rogers & Sharp, *Interaction Design*): **effective,
efficient, safe, good utility, learnable, memorable, enjoyable**. Every indicator is computed after the session from
what is already recorded (`tasks.csv`, `events.csv`, `questionnaires.csv`); nothing extra is logged and the participant
sees nothing new. The code is [hci/ux.py](../hci/ux.py); it runs at the end of every session and in `python run.py export`.

## The headline indicator per goal

| Goal | Headline indicator | Physical input it comes from | Reads as |
|---|---|---|---|
| **Effective** | `success_rate`: share of tasks answered correctly, with `target_reached` / `nav_failure` showing whether a failure was the menu's (target page never shown) or a reading error | answer, `page_view` events against the task's target pages | higher is better |
| **Efficient** | `time_to_target_s`: task start to the moment every target page has been shown, minus induced page lag | `page_view` times, `sabotage_lag` durations | lower is better |
| **Safe** | `wrong_page_rate`: wrong pages ÷ pages viewed | `page_view` events against target pages | lower is better |
| **Good utility** | `compare_ratio`: time per step in the two-page compare task ÷ time per step in lookups | task type, time to target, the menu's shortest steps | 1 = compares are supported as well as lookups; above 1 = worse |
| **Learnable** | `learning_gain`: 1 − (time per step in block-1 lookups ÷ time per step in practice) | practice and block-1 tasks of the same menu | higher = improved more after first contact |
| **Memorable** | `relearn_ratio`: time per step in block-2 lookups ÷ block-1 lookups | the same menu before and after the gap between emotion blocks | 1 or less = remembered; above 1 = forgotten |
| **Enjoyable** | `menu_rank`: preference rank of the three menus (1 = best) | the ranking after each emotion block | lower is better |

**Time per step** (`time_per_step_s`) is time to target ÷ the fewest steps that menu needs for that task
(`shortest_steps`), so a menu that needs more steps by design is not penalised for it.

## Supporting indicators

| Goal | Indicator | Meaning |
|---|---|---|
| Effective | `target_reached`, `nav_failure`, `timeout` | target pages all shown; wrong answer *and* target not reached; ran out of time |
| Efficient | `time_per_step_s`, `lostness`, `mouse_path_px` | see above; Smith's (1996) lostness `sqrt((N/S − 1)² + (R/N − 1)²)` with S pages viewed, N distinct pages, R pages required (0 = direct, above about 0.5 = lost); mouse path length |
| Safe | `backtracks`, `unexpected_closes` | returns to a page already visited; the menu closed itself because the pointer left it (only the hover drop-down M1 does this; induced "glitch" closes are not counted) |
| Good utility | `time_per_step_lookup_s`, `_extreme_s`, `_compare_s`, `success_compare` | the same cost per task type |
| Learnable | `first_use_time_to_target_s`, `first_use_wrong_pages`, `use_no` | the menu's very first task; the nth task with this menu (for learning curves) |
| Enjoyable | `tlx_frustration`, `mood_change_<item>` | the frustration rating after the sub-block; each mood item after the sub-block minus after the emotion block's induction |

## Output files (per participant)

| File | One row per | Contains |
|---|---|---|
| `ux_tasks.csv` | task (practice included) | the six label columns, `subset`, `attempt`, `task_id`, `type`, `use_no`, `t_start` and the per-task indicators |
| `ux_subblocks.csv` | sub-block = one menu in one emotion (last attempt only) | rates and means of the per-task indicators, the per-type costs, `compare_ratio`, `menu_rank`, `tlx_frustration`, `mood_change_*` |
| `ux_menus.csv` | menu | the seven headline indicators pooled over both emotion blocks, plus `first_use_*` and `tlx_frustration_mean` / `menu_rank_mean` |

`python run.py export` stacks them into `data/exports/ux_tasks_all.csv`, `ux_subblocks_all.csv` and `ux_menus_all.csv`.

## How to read them, and what they cannot tell you

- **Compare menus within an emotion.** Behaviour depends on the induced emotion as well as on the menu. Use
  `ux_subblocks.csv` (one row per menu × emotion) for the main comparison; `ux_menus.csv` pools both emotions.
- **Learnable and memorable carry the emotion with them.** `learning_gain` compares neutral practice with emotion block 1,
  `relearn_ratio` compares block 1 with block 2 (a different emotion). Both are fair *between the three menus of one
  participant*, who meet the same emotions in the same order; the counterbalancing balances emotion order over participants.
- **The three menus share one website**, so knowledge of the site carries over from menu to menu. The Latin square balances
  this across a set of six participants.
- **Time per step needs the target to be reached.** Tasks that never reach their target pages have no time to target; with
  many such tasks the efficiency, utility, learning and memory indicators become empty. Read them with `target_reached_rate`.
- **Boredom blocks have no compare task** (every task is the same lookup template), so `compare_ratio` is empty there.
- **Dropped clicks** in the frustration block still add time; only page lag is removed.
- **Utility, learnability and memorability** are only roughly captured by behaviour: the functionality is the same in every
  menu, each menu is used ten times, and there is one gap of about 15–20 minutes. A short self-report item per goal after
  each sub-block would measure them more directly (not added; it would change the protocol).
- **Enjoyable** rests on self-report. Behaviour alone cannot show that a menu was enjoyable.

## References (verify before use)

- Preece, J., Rogers, Y., & Sharp, H. *Interaction Design: Beyond Human-Computer Interaction* (usability and user-experience goals).
- Smith, P. A. (1996). Towards a practical measure of hypertext usability. *Interacting with Computers*.
- Hart, S. G. (2006). NASA-Task Load Index (NASA-TLX); 20 years later.
