"""Query order and starting looks, both decided by the participant number.

With k = n - 1 (P01 -> 0):
  query order    row k mod 5 of a cyclic Latin square: every query is in every position once per 5 participants.
  starting look  query i (in canonical order) starts in look (i + k) mod 6, so across 6 consecutive participants
                 every query starts once in every look, and every participant starts in 5 different looks.
"""

import re

PID_PATTERN = re.compile(r"^P(\d{2,3})$")


def participant_number(pid):
    m = PID_PATTERN.match(pid)
    if not m:
        raise ValueError(f"Participant ID must look like P01 (got '{pid}')")
    n = int(m.group(1))
    if n < 1:
        raise ValueError("Participant numbers start at P01")
    return n


def assign(pid, queries, looks):
    k = participant_number(pid) - 1
    shift = k % len(queries)
    order = queries[shift:] + queries[:shift]
    start = {q: looks[(i + k) % len(looks)] for i, q in enumerate(queries)}
    return {"order_scheme": shift + 1, "look_scheme": k % len(looks) + 1, "order": order, "start_looks": start}
