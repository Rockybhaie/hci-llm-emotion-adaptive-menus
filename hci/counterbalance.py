"""2 x 2 Latin square over emotion order and task-set order.

Participant numbers cycle through the four schemes, so any 4 consecutive
participants (P01-P04, P05-P08) are fully balanced.
"""

import re

SCHEMES = [
    # (emotion order, task-set order)
    ((0, 1), ("A", "B")),
    ((1, 0), ("A", "B")),
    ((0, 1), ("B", "A")),
    ((1, 0), ("B", "A")),
]

PID_PATTERN = re.compile(r"^P(\d{2,3})$")


def participant_number(pid):
    m = PID_PATTERN.match(pid)
    if not m:
        raise ValueError(f"Participant ID must look like P01 (got '{pid}')")
    n = int(m.group(1))
    if n < 1:
        raise ValueError("Participant numbers start at P01")
    return n


def assign(pid, emotions):
    """Return the block plan for one participant: [(emotion, task_set), (emotion, task_set)]."""
    n = participant_number(pid)
    index = (n - 1) % len(SCHEMES)
    order, sets = SCHEMES[index]
    return {
        "scheme": index + 1,
        "blocks": [{"emotion": emotions[o], "task_set": s} for o, s in zip(order, sets)],
    }
