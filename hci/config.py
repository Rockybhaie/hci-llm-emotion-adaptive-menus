"""Loading config/genui.yaml (the study) and config/devices.yaml (the sensors)."""

from dataclasses import dataclass

import yaml

from . import paths


class ConfigError(Exception):
    pass


def _yaml(path):
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        raise ConfigError(f"Missing config file: {paths.rel(path)}")


@dataclass(frozen=True)
class Config:
    study: dict       # config/genui.yaml
    devices: dict     # config/devices.yaml

    @property
    def queries(self):
        return list(self.study["queries"])

    @property
    def looks(self):
        return list(self.study["looks"])

    @property
    def adaptation(self):
        return self.study["adaptation"]

    def timing(self, key, fast=False):
        value = self.study["timings"][key]
        return round(value / self.study["fast_divisor"], 2) if fast else value


def load():
    cfg = Config(study=_yaml(paths.CONFIG / "genui.yaml"), devices=_yaml(paths.CONFIG / "devices.yaml"))
    if len(cfg.queries) != len(set(cfg.queries)):
        raise ConfigError("config/genui.yaml: each query may appear only once")
    if len(cfg.looks) < 2:
        raise ConfigError("config/genui.yaml: at least two looks are needed")
    return cfg
