"""The answer content: content/queries/<id>.yaml, each answer written in six looks as a list of blocks.

The block format is the contract shared with the renderer (web/genui/render.js) and, later, with the
LLM agent, which will produce the same blocks live. `validate()` rejects anything the renderer cannot draw.
"""

from functools import lru_cache

import yaml

from . import paths
from .config import ConfigError

CONTENT = paths.ROOT / "content" / "queries"

CHART_KINDS = {"bar", "line", "scatter", "histogram", "box"}
DIAGRAM_KINDS = {"network", "flow", "tree", "cycle", "timeline"}
TONES = {"tip", "note", "analogy", "warning"}


@lru_cache(maxsize=None)
def load_query(query_id):
    path = CONTENT / f"{query_id}.yaml"
    if not path.exists():
        raise ConfigError(f"Missing content file: {paths.rel(path)}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _need(cond, where, msg):
    if not cond:
        raise ConfigError(f"{where}: {msg}")


def _text(value, where, field):
    _need(isinstance(value, str) and value.strip(), where, f"'{field}' must be non-empty text")


def validate_block(block, where):
    _need(isinstance(block, dict) and "type" in block, where, "every block needs a 'type'")
    t = block["type"]
    if t in ("heading", "paragraph"):
        _text(block.get("text"), where, "text")
    elif t == "bullets":
        _need(block.get("items") and all(isinstance(i, str) for i in block["items"]), where, "bullets need text items")
    elif t == "steps":
        items = block.get("items") or []
        _need(items, where, "steps need items")
        for i in items:
            _need(isinstance(i, dict) and i.get("title") and i.get("text"), where, "each step needs title and text")
    elif t == "table":
        cols = block.get("columns") or []
        rows = block.get("rows") or []
        _need(cols and rows, where, "tables need columns and rows")
        for r in rows:
            _need(len(r) == len(cols), where,
                  f"row {r!r} has {len(r)} cells but there are {len(cols)} columns (quote text that contains commas)")
    elif t == "chart":
        kind = block.get("kind")
        _need(kind in CHART_KINDS, where, f"chart kind must be one of {sorted(CHART_KINDS)}")
        if kind == "bar":
            cats, vals = block.get("categories") or [], block.get("values") or []
            _need(cats and len(cats) == len(vals), where, "bar charts need matching categories and values")
            _need(all(isinstance(v, (int, float)) for v in vals), where, "bar values must be numbers")
        elif kind in ("line", "scatter"):
            series = block.get("series") or []
            _need(series, where, f"{kind} charts need series")
            for s in series:
                pts = s.get("points") or []
                _need(pts and all(len(p) == 2 for p in pts), where, "series points must be [x, y] pairs")
        else:
            vals = block.get("values") or []
            _need(len(vals) >= 3 and all(isinstance(v, (int, float)) for v in vals), where,
                  f"{kind} charts need at least 3 numeric values")
    elif t == "callout":
        _need(block.get("tone", "note") in TONES, where, f"callout tone must be one of {sorted(TONES)}")
        _text(block.get("text"), where, "text")
    elif t == "example":
        _text(block.get("title"), where, "title")
        _need(block.get("steps"), where, "examples need steps")
        _text(block.get("result"), where, "result")
    elif t == "formula":
        _text(block.get("expression"), where, "expression")
    elif t == "cards":
        items = block.get("items") or []
        _need(items and all(i.get("title") and i.get("text") for i in items), where, "cards need title and text")
    elif t == "diagram":
        kind = block.get("kind")
        _need(kind in DIAGRAM_KINDS, where, f"diagram kind must be one of {sorted(DIAGRAM_KINDS)}")
        if kind == "network":
            _need(block.get("layers") and all(isinstance(n, int) and 0 < n <= 8 for n in block["layers"]), where,
                  "network layers must be 1-8 neurons each")
        elif kind == "flow":
            _need(len(block.get("nodes") or []) >= 2, where, "flow diagrams need at least 2 nodes")
        elif kind == "cycle":
            _need(3 <= len(block.get("nodes") or []) <= 8, where, "cycle diagrams need 3-8 nodes")
        elif kind == "timeline":
            total = block.get("total")
            items = block.get("items") or []
            _need(isinstance(total, int) and total > 0 and items, where, "timelines need a whole-number total and items")
            for i in items:
                _need(isinstance(i, dict) and i.get("label") and 1 <= i.get("from", 0) <= i.get("to", 0) <= total,
                      where, f"timeline item {i!r} needs a label and 1 <= from <= to <= total")
        else:
            _text(block.get("root"), where, "root")
            _need(block.get("branches") and all(b.get("label") and b.get("leaves") for b in block["branches"]),
                  where, "tree branches need label and leaves")
    else:
        raise ConfigError(f"{where}: unknown block type '{t}'")


def validate(query_id, looks):
    q = load_query(query_id)
    where = f"content/queries/{query_id}.yaml"
    _need(q.get("id") == query_id, where, "id must match the file name")
    _text(q.get("query"), where, "query")
    _text(q.get("type"), where, "type")
    quiz = q.get("quiz") or {}
    _text(quiz.get("question"), where, "quiz.question")
    _need(len(quiz.get("options") or []) >= 2, where, "the quiz needs at least 2 options")
    _need(quiz.get("answer") in quiz["options"], where, "quiz.answer must be one of the options")
    _need(len(set(quiz["options"])) == len(quiz["options"]), where, "quiz options must be different")
    missing = [lk for lk in looks if lk not in (q.get("looks") or {})]
    _need(not missing, where, f"missing looks: {missing}")
    for look in looks:
        blocks = q["looks"][look]
        _need(isinstance(blocks, list) and blocks, where, f"look '{look}' has no blocks")
        for i, b in enumerate(blocks):
            validate_block(b, f"{where} · {look} · block {i + 1}")
    return q


def client_view(query_id, looks):
    """What the browser may see: everything except the quiz answer."""
    q = load_query(query_id)
    quiz = {k: v for k, v in q["quiz"].items() if k != "answer"}
    return {"id": q["id"], "type": q["type"], "subject": q.get("subject", ""), "query": q["query"], "quiz": quiz,
            "looks": {lk: q["looks"][lk] for lk in looks}}


def word_count(blocks):
    """Rough reading length of a look (for keeping the six looks comparable)."""
    words = 0

    def walk(v):
        nonlocal words
        if isinstance(v, str):
            words += len(v.split())
        elif isinstance(v, dict):
            for k, x in v.items():
                if k not in ("type", "kind", "tone", "values", "points", "layers"):
                    walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(blocks)
    return words
