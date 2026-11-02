"""Deterministic assignment of emotion order, menu order and task subsets.

Participant numbers within a group cycle through six schemes, so P01-P06 (and P07-P12, ...) are
one complete balanced set:

  emotion order : 2 options, menu order : 3 options (cyclic Latin square rows)
  scheme k = (n - 1) % 6 uses emotion order k % 2 and menu order k % 3; because 2 and 3 are coprime
  the six schemes are exactly the six combinations.

Both emotion blocks of one participant use the same menu order.

Task subsets: there are six (S1-S6) and six cells (2 emotions x 3 menus). Participant k gives cell
c = emotion_index * 3 + menu_index the subset (c + k) % 6. So
  * each participant meets every subset exactly once (cells differ -> all six residues), and
  * across a complete set of six participants each cell sees every subset exactly once, which makes
    each subset appear with each menu twice and with each emotion three times.
"""

import re

PID_PATTERN = re.compile(r"^P(\d{2,3})$")

SCHEME_COUNT = 6
MENU_ORDERS = [(0, 1, 2), (1, 2, 0), (2, 0, 1)]     # cyclic Latin square: each menu once per position
EMOTION_ORDERS = [(0, 1), (1, 0)]
SUBSETS = [f"S{i}" for i in range(1, 7)]
SUBBLOCKS = 3


def participant_number(pid):
    m = PID_PATTERN.match(pid)
    if not m:
        raise ValueError(f"Participant ID must look like P01 (got '{pid}')")
    n = int(m.group(1))
    if n < 1:
        raise ValueError("Participant numbers start at P01")
    return n


def subset_for(scheme_index, emotion_index, menu_index):
    return SUBSETS[(emotion_index * 3 + menu_index + scheme_index) % 6]


def assign(pid, emotions, menus):
    """Full plan for one participant.

    emotions: the group's two emotions; menus: the group's three menu ids (their list order is each
    menu's identity in the counterbalancing).
    """
    n = participant_number(pid)
    k = (n - 1) % SCHEME_COUNT
    emotion_order = EMOTION_ORDERS[k % 2]
    menu_order = MENU_ORDERS[k % 3]
    blocks = []
    for pos, e in enumerate(emotion_order, start=1):
        blocks.append({
            "no": pos,
            "emotion": emotions[e],
            "sub_blocks": [{"sub_block": s, "menu": menus[m], "subset": subset_for(k, e, m)}
                           for s, m in enumerate(menu_order, start=1)],
        })
    return {
        "scheme": k + 1,
        "participant_number": n,
        "emotion_order": [emotions[e] for e in emotion_order],
        "menu_order": [menus[m] for m in menu_order],
        "practice": [{"menu": menus[m], "pool": [2 * m, 2 * m + 1]} for m in menu_order],
        "blocks": blocks,
    }


def describe(plan):
    """One line per sub-block, for the researcher's terminal and plan.txt."""
    lines = [f"scheme {plan['scheme']} of {SCHEME_COUNT}: emotion order {' > '.join(plan['emotion_order'])}, "
             f"menu order {' > '.join(plan['menu_order'])}"]
    for b in plan["blocks"]:
        cells = "   ".join(f"{s['sub_block']}: {s['menu']}/{s['subset']}" for s in b["sub_blocks"])
        lines.append(f"  block {b['no']} ({b['emotion']}): {cells}")
    return "\n".join(lines)
