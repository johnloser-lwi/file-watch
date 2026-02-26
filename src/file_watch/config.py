"""Configuration loading, merging, and validation."""

from __future__ import annotations

import fnmatch
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]


VALID_CONFLICT_STRATEGIES = ("skip", "overwrite", "rename")
VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


def _normalize_ext(ext: str) -> str:
    """Normalize extension to lowercase with a leading dot."""
    ext = ext.strip().lower()
    if ext and not ext.startswith("."):
        ext = "." + ext
    return ext


@dataclass(frozen=True)
class Route:
    """Maps a set of file extensions to a destination directory.

    An empty ``extensions`` tuple is a catch-all that matches every file.
    Catch-all routes must be placed last — earlier routes take priority.
    """
    destination: str
    extensions: tuple  # tuple[str, ...] — normalized lowercase with dot

    @property
    def is_catch_all(self) -> bool:
        return len(self.extensions) == 0

    def matches(self, path: str) -> bool:
        if self.is_catch_all:
            return True
        return Path(path).suffix.lower() in self.extensions


@dataclass(frozen=True)
class Config:
    source: str
    routes: tuple  # tuple[Route, ...]
    stable_for: float = 5.0
    poll_interval: float = 1.0
    max_wait: float = 0.0
    on_conflict: str = "rename"
    rename_template: str = "{stem}_{n}{suffix}"
    log_level: str = "INFO"
    log_file: str = ""
    log_max_bytes: int = 10_485_760
    log_backup_count: int = 3
    dry_run: bool = False
    ignore_extensions: tuple = ()  # tuple[str, ...] — normalized
    ignore_patterns: tuple = ()    # tuple[str, ...] — fnmatch glob patterns


def find_route(path: str, routes: tuple) -> Optional[Route]:
    """Return the first Route that matches *path*, or None if no match."""
    for route in routes:
        if route.matches(path):
            return route
    return None


def is_ignored(path: str, ignore_extensions: tuple, ignore_patterns: tuple) -> bool:
    """Return True if *path* matches any ignore rule."""
    name = Path(path).name
    ext = Path(path).suffix.lower()
    if ext in ignore_extensions:
        return True
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def default_config_path() -> Optional[Path]:
    """Return the platform user config path (may not exist)."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return Path(appdata) / "file-watch" / "config.toml"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "file-watch" / "config.toml"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME", "")
        base = Path(xdg) if xdg else Path.home() / ".config"
        return base / "file-watch" / "config.toml"
    return None


def find_config_file(explicit_path: Optional[str] = None) -> Optional[Path]:
    """Resolve config file using search order: explicit > cwd > platform default."""
    if explicit_path:
        p = Path(explicit_path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {explicit_path}")
        return p

    cwd_config = Path("file-watch.toml")
    if cwd_config.exists():
        return cwd_config

    platform_path = default_config_path()
    if platform_path and platform_path.exists():
        return platform_path

    return None


def _load_toml(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def _parse_routes(raw_routes: list) -> tuple:
    """Convert a ``[[routes]]`` TOML array into a tuple of Route objects."""
    result = []
    for r in raw_routes:
        dest = r.get("destination", "")
        exts = tuple(_normalize_ext(e) for e in r.get("extensions", []))
        result.append(Route(destination=dest, extensions=exts))
    return tuple(result)


def load_config(
    config_path: Optional[str] = None,
    *,
    source: Optional[str] = None,
    destination: Optional[str] = None,
    stable_for: Optional[float] = None,
    poll_interval: Optional[float] = None,
    max_wait: Optional[float] = None,
    on_conflict: Optional[str] = None,
    rename_template: Optional[str] = None,
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    dry_run: bool = False,
    ignore_extensions: Sequence[str] = (),
    ignore_patterns: Sequence[str] = (),
) -> Config:
    """Load config from file (if found) then overlay CLI arguments.

    Route resolution precedence
    ---------------------------
    1. ``[[routes]]`` array in the TOML file (ordered, first match wins).
    2. ``[watch].destination`` (old single-destination style) → implicit catch-all.
    3. ``-d/--destination`` CLI flag → replaces any existing catch-all and appends
       a new one at the end so typed routes still take priority.

    Ignore rule precedence
    ----------------------
    CLI ``--ignore-ext`` / ``--ignore-pattern`` values are *appended* to whatever
    the config file defines (not replaced).
    """
    found = find_config_file(config_path)
    raw: dict = {}
    if found:
        raw = _load_toml(found)

    watch = raw.get("watch", {})
    move = raw.get("move", {})
    logging_section = raw.get("logging", {})
    ignore_section = raw.get("ignore", {})
    raw_routes = raw.get("routes", [])

    # --- Source ---
    cfg_source = source or watch.get("source", "")

    # --- Routes ---
    routes_from_toml = _parse_routes(raw_routes)

    # Backward-compat: [watch].destination → implicit catch-all when no [[routes]]
    watch_dest = watch.get("destination", "")
    if watch_dest and not routes_from_toml:
        routes_from_toml = (Route(destination=watch_dest, extensions=()),)

    # CLI -d overrides / replaces any existing catch-all and appends at end
    if destination:
        non_catchall = tuple(r for r in routes_from_toml if not r.is_catch_all)
        cfg_routes = non_catchall + (Route(destination=destination, extensions=()),)
    else:
        cfg_routes = routes_from_toml

    # --- Ignore rules: TOML + CLI (additive) ---
    toml_ignore_exts = tuple(
        _normalize_ext(e) for e in ignore_section.get("extensions", [])
    )
    cli_ignore_exts = tuple(_normalize_ext(e) for e in ignore_extensions)
    all_ignore_exts = tuple(dict.fromkeys(toml_ignore_exts + cli_ignore_exts))

    toml_ignore_pats = tuple(ignore_section.get("patterns", []))
    cli_ignore_pats = tuple(ignore_patterns)
    all_ignore_pats = tuple(dict.fromkeys(toml_ignore_pats + cli_ignore_pats))

    # --- Scalar settings ---
    cfg_stable_for = stable_for if stable_for is not None else float(watch.get("stable_for", 5.0))
    cfg_poll_interval = (
        poll_interval if poll_interval is not None else float(watch.get("poll_interval", 1.0))
    )
    cfg_max_wait = max_wait if max_wait is not None else float(watch.get("max_wait", 0.0))
    cfg_on_conflict = on_conflict or move.get("on_conflict", "rename")
    cfg_rename_template = rename_template or move.get("rename_template", "{stem}_{n}{suffix}")
    cfg_log_level = (log_level or logging_section.get("level", "INFO")).upper()
    cfg_log_file = log_file if log_file is not None else logging_section.get("log_file", "")
    cfg_log_max_bytes = int(logging_section.get("log_max_bytes", 10_485_760))
    cfg_log_backup_count = int(logging_section.get("log_backup_count", 3))

    cfg = Config(
        source=cfg_source,
        routes=cfg_routes,
        stable_for=cfg_stable_for,
        poll_interval=cfg_poll_interval,
        max_wait=cfg_max_wait,
        on_conflict=cfg_on_conflict,
        rename_template=cfg_rename_template,
        log_level=cfg_log_level,
        log_file=cfg_log_file,
        log_max_bytes=cfg_log_max_bytes,
        log_backup_count=cfg_log_backup_count,
        dry_run=dry_run,
        ignore_extensions=all_ignore_exts,
        ignore_patterns=all_ignore_pats,
    )

    validate_config(cfg)
    return cfg


def validate_config(cfg: Config) -> None:
    """Raise ValueError for invalid configuration."""
    if not cfg.source:
        raise ValueError("source path is required (set in config file or via -s/--source)")
    if not cfg.routes:
        raise ValueError(
            "at least one route (destination) is required — "
            "add [[routes]] in config file or use -d/--destination"
        )

    src = Path(cfg.source).resolve()

    for i, route in enumerate(cfg.routes):
        if not route.destination:
            raise ValueError(f"route[{i}] has an empty destination")
        dst = Path(route.destination).resolve()
        if src == dst:
            raise ValueError(
                f"source and destination must differ: "
                f"route[{i}] destination equals source ({src})"
            )

    # A non-terminal catch-all shadows every route after it
    for i, route in enumerate(cfg.routes[:-1]):
        if route.is_catch_all:
            raise ValueError(
                f"route[{i}] is a catch-all but is not the last route — "
                "it would shadow all subsequent routes"
            )

    if cfg.stable_for <= 0:
        raise ValueError(f"stable_for must be positive, got {cfg.stable_for}")
    if cfg.poll_interval <= 0:
        raise ValueError(f"poll_interval must be positive, got {cfg.poll_interval}")
    if cfg.max_wait < 0:
        raise ValueError(f"max_wait must be >= 0, got {cfg.max_wait}")

    if cfg.on_conflict not in VALID_CONFLICT_STRATEGIES:
        raise ValueError(
            f"on_conflict must be one of {VALID_CONFLICT_STRATEGIES}, got {cfg.on_conflict!r}"
        )

    if cfg.on_conflict == "rename":
        if "{n}" not in cfg.rename_template and "{ts}" not in cfg.rename_template:
            raise ValueError(
                "rename_template must contain {n} or {ts} to avoid infinite loops"
            )

    if cfg.log_level not in VALID_LOG_LEVELS:
        raise ValueError(
            f"log level must be one of {VALID_LOG_LEVELS}, got {cfg.log_level!r}"
        )
