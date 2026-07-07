from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dev_tools.github import GhError, Project, parse_project


APP_NAME = "dev-tools"
CONFIG_FILE = "config.json"


@dataclass(frozen=True)
class Config:
    default_project: Project | None = None


def config_path() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        base = Path(xdg_config_home).expanduser()
        if not base.is_absolute():
            base = Path.home() / ".config"
    else:
        base = Path.home() / ".config"
    return base / APP_NAME / CONFIG_FILE


def load_config(path: Path | None = None) -> Config:
    path = path or config_path()
    if not path.exists():
        return Config()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise GhError(f"could not read config at {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise GhError(f"config at {path} is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise GhError(f"config at {path} must contain a JSON object")

    default_project = raw.get("default_project")
    if default_project is None:
        return Config()
    if not isinstance(default_project, str):
        raise GhError(f"config at {path} has invalid default_project")
    return Config(default_project=parse_project(default_project))


def save_default_project(project: Project, path: Path | None = None) -> Path:
    path = path or config_path()
    data = _load_raw_config(path)
    data["default_project"] = project.slug
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _load_raw_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise GhError(f"could not read config at {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise GhError(f"config at {path} is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise GhError(f"config at {path} must contain a JSON object")
    return raw
