from __future__ import annotations

import json
from pathlib import Path

import pytest

from dev_tools.config import Config, config_path, load_config, save_default_project
from dev_tools.github import GhError, Project


def test_config_path_uses_xdg_config_home(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert config_path() == tmp_path / "dev-tools" / "config.json"


def test_config_path_falls_back_for_relative_xdg_config_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", "relative")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    assert config_path() == tmp_path / ".config" / "dev-tools" / "config.json"


def test_load_config_missing_file() -> None:
    assert load_config(path=Path("missing")) == Config()


def test_load_config_default_project(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"default_project": "github.example.com/org/repo"}', encoding="utf-8")

    assert load_config(path=path) == Config(
        default_project=Project(owner="org", repo="repo", host="github.example.com")
    )


def test_load_config_rejects_invalid_json(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(GhError, match="not valid JSON"):
        load_config(path=path)


def test_save_default_project_preserves_other_config(tmp_path) -> None:
    path = tmp_path / "dev-tools" / "config.json"
    path.parent.mkdir()
    path.write_text('{"other": true}', encoding="utf-8")

    saved_path = save_default_project(Project(owner="clemux", repo="plant-manager"), path=path)

    assert saved_path == path
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "default_project": "clemux/plant-manager",
        "other": True,
    }


def test_save_default_project_creates_parent(tmp_path) -> None:
    path = tmp_path / "dev-tools" / "config.json"

    save_default_project(Project(owner="org", repo="repo", host="github.example.com"), path=path)

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "default_project": "github.example.com/org/repo"
    }
