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
    groups: dict      # G1 -> {site, tasks, emotions}
    emotions: dict    # stress -> {arousal, induction, in_task}
    washout: dict
    devices: dict

    def group(self, group_id):
        try:
            return self.groups[group_id]
        except KeyError:
            raise ConfigError(f"Unknown group '{group_id}'. Choose one of: {', '.join(self.groups)}")

    def timing(self, key, fast=False):
        value = self.experiment["timings"][key]
        return max(3, round(value / self.experiment["fast_divisor"])) if fast else value


def load():
    groups_cfg = _yaml(paths.CONFIG / "groups.yaml")
    cfg = Config(
        experiment=_yaml(paths.CONFIG / "experiment.yaml"),
        groups=groups_cfg["groups"],
        emotions=groups_cfg["emotions"],
        washout=groups_cfg["washout"],
        devices=_yaml(paths.CONFIG / "devices.yaml"),
    )
    for gid, g in cfg.groups.items():
        if len(g["emotions"]) != 2:
            raise ConfigError(f"{gid} must have exactly two emotions")
        for e in g["emotions"]:
            if e not in cfg.emotions:
                raise ConfigError(f"{gid} uses emotion '{e}' which is not defined in groups.yaml")
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
