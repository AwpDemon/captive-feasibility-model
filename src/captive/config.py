"""Load the single YAML assumptions file and apply dotted-path overrides.

Every assumption in the model lives in ``config/assumptions.yaml``. Scenarios,
stress tests and the tornado chart never edit that file; they apply *overrides*
such as ``{"economics.discount_rate": 0.08}`` to a deep copy of it, so every run is
reproducible from (file, overrides, seed).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "assumptions.yaml"

REQUIRED_SECTIONS = (
    "meta",
    "company",
    "economics",
    "lines",
    "program_costs",
    "captive",
    "domiciles",
    "programs",
)


def load_config(path: str | Path | None = None) -> dict:
    path = Path(path) if path else DEFAULT_CONFIG
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    validate(cfg)
    return cfg


def validate(cfg: dict) -> None:
    missing = [s for s in REQUIRED_SECTIONS if s not in cfg]
    if missing:
        raise ValueError(f"config is missing sections: {missing}")
    if cfg["meta"]["n_sims"] < 1000:
        raise ValueError("n_sims must be at least 1,000")
    for name, line in cfg["lines"].items():
        pattern = line["payout_pattern"]
        if abs(sum(pattern) - 1.0) > 1e-6:
            raise ValueError(f"payout pattern for {name} sums to {sum(pattern):.4f}, not 1")
    ids = [p["id"] for p in cfg["programs"]]
    if len(ids) != len(set(ids)):
        raise ValueError("program ids must be unique")
    for p in cfg["programs"]:
        if p["type"] not in ("guaranteed_cost", "large_deductible", "captive"):
            raise ValueError(f"unknown program type {p['type']!r}")
        if p["type"] == "captive" and p.get("domicile", cfg["captive"]["base_domicile"]) not in cfg["domiciles"]:
            raise ValueError(f"program {p['id']} uses an unknown domicile")
        for line in p.get("retention", {}):
            if line not in cfg["lines"]:
                raise ValueError(f"program {p['id']} sets a retention for unknown line {line!r}")


def _walk(node: Any, key: str) -> Any:
    if isinstance(node, list):
        return node[int(key)]
    return node[key]


def get_path(cfg: dict, dotted: str) -> Any:
    node = cfg
    for key in dotted.split("."):
        node = _walk(node, key)
    return node


def set_path(cfg: dict, dotted: str, value: Any) -> None:
    keys = dotted.split(".")
    node = cfg
    for key in keys[:-1]:
        node = _walk(node, key)
    last = keys[-1]
    if isinstance(node, list):
        node[int(last)] = value
    else:
        if last not in node:
            raise KeyError(f"override path {dotted!r} does not exist in the config")
        node[last] = value


def with_overrides(cfg: dict, overrides: dict | None) -> dict:
    """Deep-copy ``cfg`` and apply ``{"a.b.c": value}`` overrides."""
    out = copy.deepcopy(cfg)
    for path, value in (overrides or {}).items():
        set_path(out, path, value)
    validate(out)
    return out


def flatten(node: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """Flatten a nested config to (dotted path, scalar) pairs for the Excel sheet."""
    rows: list[tuple[str, Any]] = []
    if isinstance(node, dict):
        for k, v in node.items():
            rows.extend(flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(node, list) and node and all(isinstance(x, (int, float)) for x in node):
        rows.append((prefix, ", ".join(f"{x:g}" for x in node)))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            rows.extend(flatten(v, f"{prefix}.{i}"))
    else:
        rows.append((prefix, node))
    return rows
