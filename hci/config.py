"""Loading and validating everything under config/ and web/sites/."""

import json
from dataclasses import dataclass
from functools import lru_cache

import yaml

from . import paths


class ConfigError(Exception):
    pass


def _yaml(path):
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        raise ConfigError(f"Missing config file: {path.relative_to(paths.ROOT)}")


@dataclass(frozen=True)
class Config:
    experiment: dict
    groups: dict      # G1 -> {site, tasks, emotions, menus}
    emotions: dict    # stress -> {arousal, induction, booster, in_task}
    washout: dict
    menus: dict       # M1 -> {group, type, name, label, how, params}

    def group(self, group_id):
        try:
            return self.groups[group_id]
        except KeyError:
            raise ConfigError(f"Unknown group '{group_id}'. Choose one of: {', '.join(self.groups)}")

    def menu(self, menu_id):
        try:
            return self.menus[menu_id]
        except KeyError:
            raise ConfigError(f"Unknown menu '{menu_id}'. Choose one of: {', '.join(self.menus)}")

    def timing(self, key, fast=False):
        value = self.experiment["timings"][key]
        return max(3, round(value / self.experiment["fast_divisor"])) if fast else value


def load():
    from . import menus as menu_models
    groups_cfg = _yaml(paths.CONFIG / "groups.yaml")
    cfg = Config(
        experiment=_yaml(paths.CONFIG / "experiment.yaml"),
        groups=groups_cfg["groups"],
        emotions=groups_cfg["emotions"],
        washout=groups_cfg["washout"],
        menus=_yaml(paths.CONFIG / "menus.yaml"),
    )
    for mid, m in cfg.menus.items():
        if m["type"] not in menu_models.MODELS:
            raise ConfigError(f"Menu {mid} has unknown type '{m['type']}'")
    for gid, g in cfg.groups.items():
        if len(g["emotions"]) != 2:
            raise ConfigError(f"{gid} must have exactly two emotions")
        for e in g["emotions"]:
            if e not in cfg.emotions:
                raise ConfigError(f"{gid} uses emotion '{e}' which is not defined in groups.yaml")
            if "booster" not in cfg.emotions[e]:
                raise ConfigError(f"Emotion '{e}' has no booster defined in groups.yaml")
        if len(g.get("menus", [])) != 3:
            raise ConfigError(f"{gid} must list exactly three menus")
        for mid in g["menus"]:
            if mid not in cfg.menus:
                raise ConfigError(f"{gid} uses menu '{mid}' which is not defined in menus.yaml")
            if cfg.menus[mid]["group"] != gid:
                raise ConfigError(f"Menu {mid} belongs to {cfg.menus[mid]['group']}, not {gid} "
                                  f"(menus are nested within groups)")
    return cfg


@lru_cache(maxsize=None)
def load_site(site_id):
    path = paths.SITES / site_id / "site.json"
    if not path.exists():
        raise ConfigError(f"Missing site content: {path.relative_to(paths.ROOT)}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_tasks(task_file):
    return _yaml(paths.CONFIG / "tasks" / task_file)
