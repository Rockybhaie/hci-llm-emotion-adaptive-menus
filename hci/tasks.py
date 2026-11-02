"""Turn config/tasks/*.yaml into concrete tasks with answers and answer options.

Answers are derived from the site content, so editing site.json can never leave
a task with a stale answer. Resolution errors are raised at start-up, not mid-session.
"""

import random
import re

from . import menus
from .config import ConfigError

NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def index_pages(site):
    pages = {}
    for section in site["sections"]:
        for page in section["pages"]:
            pages[f"{section['id']}/{page['id']}"] = {**page, "section_title": section["title"]}
    return pages


def _numeric(value, where):
    m = NUMBER.search(value)
    if not m:
        raise ConfigError(f"{where}: '{value}' has no number to compare")
    return float(m.group().replace(",", ""))


def _item(pages, page_id, name, where):
    page = pages.get(page_id)
    if page is None:
        raise ConfigError(f"{where}: unknown page '{page_id}'")
    for item in page["items"]:
        if item["name"] == name:
            return page, item
    raise ConfigError(f"{where}: no item named '{name}' on page '{page_id}'")


def _field(item, field, where):
    if field not in item["values"]:
        raise ConfigError(f"{where}: '{item['name']}' has no field '{field}'")
    return item["values"][field]


def _question(site, field, override=None):
    return override or site.get("questions", {}).get(field) or f"What is its {field.lower()}?"


def _value_options(site, pages, page, field, answer, rng):
    """Correct value plus 3 distractors: same page first, then the rest of the site."""
    local = [i["values"].get(field) for i in page["items"]]
    site_wide = [i["values"].get(field) for p in pages.values() for i in p["items"]]
    distractors = []
    for pool in (local, site_wide):
        pool = [v for v in dict.fromkeys(pool) if v and v != answer and v not in distractors]
        rng.shuffle(pool)
        distractors.extend(pool[: 3 - len(distractors)])
        if len(distractors) == 3:
            break
    options = distractors + [answer]
    rng.shuffle(options)
    return options


def _pick(pairs, mode, where):
    """Name of the item with the highest/lowest value; `pairs` = [(item, field), ...] (fields may differ)."""
    scored = [(_numeric(_field(i, f, where), where), i["name"]) for i, f in pairs]
    best = (max if mode == "max" else min)(scored)
    if sum(1 for s, _ in scored if s == best[0]) > 1:
        raise ConfigError(f"{where}: tie on {', '.join(sorted({f for _, f in pairs}))}, the answer would be ambiguous")
    return best[1]


def resolve(site, spec, rng):
    pages = index_pages(site)
    where = f"{site['id']} task {spec['id']}"
    kind = spec["type"]
    task = {"id": spec["id"], "type": kind, "field": spec["field"], "text": spec["text"]}

    if kind == "lookup":
        page, item = _item(pages, spec["page"], spec["item"], where)
        answer = _field(item, spec["field"], where)
        task.update(targets=[spec["page"]], question=_question(site, spec["field"], spec.get("question")),
                    answer=answer, options=_value_options(site, pages, page, spec["field"], answer, rng))
    elif kind == "extreme":
        page = pages.get(spec["page"])
        if page is None:
            raise ConfigError(f"{where}: unknown page '{spec['page']}'")
        names = [i["name"] for i in page["items"]]
        rng.shuffle(names)
        task.update(targets=[spec["page"]], question="", options=names,
                    answer=_pick([(i, spec["field"]) for i in page["items"]], spec["mode"], where))
    elif kind == "compare":
        found = [_item(pages, x["page"], x["item"], where) for x in spec["items"]]
        names = [it["name"] for _, it in found]
        # each item may name its own field (a fee on one page against a deposit on another)
        pairs = [(it, x.get("field", spec["field"])) for (_, it), x in zip(found, spec["items"])]
        task.update(targets=list(dict.fromkeys(x["page"] for x in spec["items"])), question="",
                    options=names, answer=_pick(pairs, spec["mode"], where))
    else:
        raise ConfigError(f"{where}: unknown task type '{kind}'")
    return task


def to_repetitive(site, spec, rng):
    """Boredom variant: same target page and item, but always the same dull template and field."""
    rep = site["repetitive"]
    if spec["type"] == "lookup":
        page_id, name = spec["page"], spec["item"]
    elif spec["type"] == "compare":
        page_id, name = spec["items"][0]["page"], spec["items"][0]["item"]
    else:
        page_id = spec["page"]
        name = resolve(site, spec, random.Random(0))["answer"]
    page = index_pages(site)[page_id]
    text = rep["template"].format(item=name, page=page["title"])
    return resolve(site, {"id": spec["id"] + "R", "type": "lookup", "page": page_id, "item": name,
                          "field": rep["field"], "text": text}, rng)


def build_subset(site, task_cfg, subset, variant=None, seed=0, menu_type=None):
    """Resolve one subset (S1-S6, or the practice pool P) into concrete tasks.

    With `menu_type` every task also carries the fewest clicks and steps that menu needs to visit its
    target pages from the home page (hci/menus.py).
    """
    if subset not in task_cfg:
        raise ConfigError(f"{site['id']}: task subset '{subset}' not found")
    rng = random.Random(seed)
    specs = task_cfg[subset]
    if variant == "repetitive":
        built = [to_repetitive(site, s, rng) for s in specs]
    else:
        built = [resolve(site, s, rng) for s in specs]
    if menu_type:
        for task in built:
            task["shortest_clicks"], task["shortest_steps"] = menus.shortest(menu_type, task["targets"])
    return built


def client_view(task):
    """What the browser is allowed to see (no answer)."""
    return {k: v for k, v in task.items() if k != "answer"}
