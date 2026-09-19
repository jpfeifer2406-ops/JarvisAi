from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

_PROJECT_ROOT = Path(__file__).parent.parent
_BASE_CONFIG = _PROJECT_ROOT / "config.yaml"
_LOCAL_CONFIG = Path(__file__).parent / "data" / "local_config.yaml"
_MISSING = object()


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config root must be a mapping: {path}")
    return data


def _deep_merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _deep_diff(value: Any, base: Any):
    """Return the minimal local override needed to turn base into value."""
    if isinstance(value, dict) and isinstance(base, dict):
        out = {}
        for key, child in value.items():
            previous = base.get(key, _MISSING)
            diff = _deep_diff(child, previous)
            if diff is not _MISSING:
                out[key] = diff
        return out if out else _MISSING

    if base is _MISSING or value != base:
        return deepcopy(value)
    return _MISSING


def load_base_config() -> dict:
    """Load tracked repository defaults only."""
    return _read_yaml(_BASE_CONFIG)


def load_config() -> dict:
    """Load tracked defaults plus ignored machine-local overrides."""
    return _deep_merge(load_base_config(), _read_yaml(_LOCAL_CONFIG))


def save_effective_config(config: dict) -> None:
    """Persist only values that differ from tracked defaults.

    This keeps config.yaml clean so the single-folder Git updater can fast-forward
    even after settings or provider credentials were changed in the cockpit.
    """
    base = _read_yaml(_BASE_CONFIG)
    diff = _deep_diff(config, base)
    _LOCAL_CONFIG.parent.mkdir(parents=True, exist_ok=True)

    if diff is _MISSING:
        _LOCAL_CONFIG.unlink(missing_ok=True)
        return

    tmp = _LOCAL_CONFIG.with_suffix(".yaml.tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        yaml.safe_dump(diff, handle, allow_unicode=True, default_flow_style=False, sort_keys=False)
    tmp.replace(_LOCAL_CONFIG)


def local_config_path() -> Path:
    return _LOCAL_CONFIG
