"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def _isolate_user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect platform config dirs to tmp so tests never pick up a real user config."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))


@pytest.fixture
def src_dir(tmp_path: Path) -> Path:
    """Temporary source directory."""
    d = tmp_path / "source"
    d.mkdir()
    return d


@pytest.fixture
def dst_dir(tmp_path: Path) -> Path:
    """Temporary destination directory."""
    d = tmp_path / "destination"
    d.mkdir()
    return d
