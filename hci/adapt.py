"""When an answer switches look by itself, and which look it switches to.

The rule only reads the emotion stream (emotion.csv rows), so it works with any emotion source that
writes the same columns. Everything it decides is logged with the emotion snapshot that caused it:
that snapshot -> look change -> the participant's reaction is the training data for the later agent.
"""

import random
from collections import Counter


def rows_as_dicts(columns, rows):
    return [dict(zip(columns, r)) for r in rows]


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def is_negative(sample, cfg):
    if str(sample.get("face")) not in ("1", "True", "true"):
        return False
    v = _f(sample.get("valence"))
    if v is not None and v < cfg["valence_below"]:
        return True
    p = sum(_f(sample.get(f"p_{c}")) or 0.0 for c in cfg["negative_classes"])
    return p > cfg["negative_prob_above"]


def snapshot(samples, cfg):
    """Summary of a window of emotion samples (stored with every look change)."""
    faces = [s for s in samples if str(s.get("face")) in ("1", "True", "true")]
    out = {"samples": len(samples), "face_fraction": round(len(faces) / len(samples), 3) if samples else 0.0,
           "negative_fraction": round(sum(is_negative(s, cfg) for s in faces) / len(faces), 3) if faces else 0.0,
           "valence": "", "arousal": "", "dominant": ""}
    if faces:
        for key in ("valence", "arousal"):
            vals = [x for x in (_f(s.get(key)) for s in faces) if x is not None]
            out[key] = round(sum(vals) / len(vals), 4) if vals else ""
        out["dominant"] = Counter(s.get("emotion") for s in faces).most_common(1)[0][0]
        probs = {}
        for s in faces:
            for k, v in s.items():
                if k.startswith("p_") and _f(v) is not None:
                    probs[k] = probs.get(k, 0.0) + _f(v)
        out.update({k: round(v / len(faces), 4) for k, v in sorted(probs.items())})
    return out


class QueryAdapter:
    """Adaptation state for one query (one answer being read)."""

    def __init__(self, cfg, looks, start_look, rng=None):
        self.cfg = cfg
        self.looks = list(looks)
        self.current = start_look
        self.seen = [start_look]
        self.n_auto = 0
        self.last_switch = None
        self.rng = rng or random.Random()

    def window_state(self, samples, t):
        """(fires, snapshot) for the samples of the last `window` seconds before t."""
        w = self.cfg["window"]
        recent = [s for s in samples if t - w <= _f(s.get("t")) <= t]
        snap = snapshot(recent, self.cfg)
        if len(recent) < 2:
            return False, snap
        span = _f(recent[-1]["t"]) - _f(recent[0]["t"])
        covered = span >= 0.8 * w and snap["face_fraction"] >= 0.8
        return covered and snap["negative_fraction"] >= self.cfg["min_fraction"], snap

    def should_switch(self, samples, t):
        """The look to switch to now, or None. `t` is the master clock."""
        if self.n_auto >= self.cfg["max_auto_per_query"]:
            return None, None
        if self.last_switch is not None and t - self.last_switch < self.cfg["cooldown"]:
            return None, None
        fires, snap = self.window_state(samples, t)
        if not fires:
            return None, snap
        return self.next_look(), snap

    def next_look(self):
        unseen = [lk for lk in self.looks if lk not in self.seen]
        pool = unseen or [lk for lk in self.looks if lk != self.current]
        if self.cfg.get("policy", "random_unseen") != "random_unseen":
            raise ValueError(f"unknown adaptation policy {self.cfg.get('policy')}")
        return self.rng.choice(pool)

    def switched(self, to, t, auto):
        self.current = to
        if to not in self.seen:
            self.seen.append(to)
        self.last_switch = t
        if auto:
            self.n_auto += 1
