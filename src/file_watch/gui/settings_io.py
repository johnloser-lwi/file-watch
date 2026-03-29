"""Settings persistence — load / save / import / export.

Settings are stored as JSON in ``~/FileWatch/settings.json`` on both
Windows and macOS.  The file is auto-saved on every meaningful change and
auto-loaded on startup.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

SETTINGS_DIR = Path.home() / "FileWatch"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
SETTINGS_VERSION = 1


def _default_settings() -> dict[str, Any]:
    """Return a minimal default settings dict."""
    return {
        "version": SETTINGS_VERSION,
        "entries": [],
        "global": {
            "stable_for": 5.0,
            "poll_interval": 1.0,
            "max_wait": 0,
            "on_conflict": "rename",
            "rename_template": "{stem}_{n}{suffix}",
            "ignore_extensions": [".tmp", ".part", ".crdownload", ".download"],
            "ignore_patterns": ["~*", ".~*", "*.!ut", "desktop.ini", "Thumbs.db", ".DS_Store"],
        },
        "window": {
            "width": 960,
            "height": 720,
        },
    }


def _default_entry() -> dict[str, Any]:
    """Return a blank watch-entry dict."""
    return {
        "source": "",
        "destination": "",
        "operation": "move",
        "extensions": [],
        "enabled": True,
    }


# ── persistence ────────────────────────────────────────────────────────

def load_settings(path: Path | None = None) -> dict[str, Any]:
    """Load settings from *path* (default: ``~/FileWatch/settings.json``).

    Returns default settings if the file doesn't exist or is unparsable.
    """
    path = path or SETTINGS_FILE
    if not path.exists():
        log.info("No settings file found at %s — using defaults", path)
        return _default_settings()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Ensure all top-level keys are present (forward-compat)
        defaults = _default_settings()
        for key in defaults:
            data.setdefault(key, defaults[key])
        # Ensure global sub-keys are present
        g_defaults = defaults["global"]
        for key in g_defaults:
            data["global"].setdefault(key, g_defaults[key])
        log.info("Loaded settings from %s", path)
        return data
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        log.warning("Corrupt settings file %s: %s — using defaults", path, exc)
        return _default_settings()


def save_settings(data: dict[str, Any], path: Path | None = None) -> None:
    """Write *data* to *path* (default: ``~/FileWatch/settings.json``)."""
    path = path or SETTINGS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log.debug("Saved settings to %s", path)


def export_settings(data: dict[str, Any], path: Path) -> None:
    """Export settings to a user-chosen path."""
    save_settings(data, path)
    log.info("Exported settings to %s", path)


def import_settings(path: Path) -> dict[str, Any]:
    """Import settings from a user-chosen path.

    Raises ``FileNotFoundError`` if *path* does not exist and
    ``ValueError`` if it is not valid JSON.
    """
    if not path.exists():
        raise FileNotFoundError(f"Settings file not found: {path}")
    data = load_settings(path)
    # Persist as the new active settings
    save_settings(data)
    log.info("Imported settings from %s", path)
    return data


def new_entry() -> dict[str, Any]:
    """Public helper: return a fresh entry dict."""
    return _default_entry()
