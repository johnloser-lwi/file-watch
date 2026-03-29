"""Bridge between GUI settings and the file-watch watcher engine.

Converts the GUI's entry list + global settings into a ``Config`` object,
then manages the observer + stability-checker lifecycle in background threads.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Callable, Optional

from file_watch.config import Config, Route
from file_watch.logging_setup import configure_logging
from file_watch.mover import StabilityChecker
from file_watch.watcher import FileWatchHandler, start_observer

log = logging.getLogger(__name__)


class WatcherBridge:
    """Controls the watcher lifecycle from the GUI."""

    def __init__(self) -> None:
        self._observer = None
        self._checker: Optional[StabilityChecker] = None
        self._stop_event = threading.Event()
        self._running = False
        self._status_cb: Optional[Callable[[str], None]] = None

    @property
    def is_running(self) -> bool:
        return self._running

    def set_status_callback(self, cb: Callable[[str], None]) -> None:
        self._status_cb = cb

    def _set_status(self, status: str) -> None:
        if self._status_cb:
            self._status_cb(status)

    # ── Config conversion ──────────────────────────────────────────

    @staticmethod
    def build_config(
        entries: list[dict[str, Any]],
        global_settings: dict[str, Any],
    ) -> Config:
        """Convert GUI entries + global settings into a ``Config``."""
        enabled = [e for e in entries if e.get("enabled", True)]
        if not enabled:
            raise ValueError("At least one enabled entry is required.")

        # The first entry's source is THE source directory.
        # All entries become routes.
        source = enabled[0].get("source", "")
        if not source:
            raise ValueError("The first entry must have a source folder.")

        routes = []
        for e in enabled:
            exts = tuple(e.get("extensions", []))
            op = e.get("operation", "move")
            dest = e.get("destination", "")
            routes.append(Route(destination=dest, extensions=exts, operation=op))

        g = global_settings
        return Config(
            source=source,
            routes=tuple(routes),
            stable_for=float(g.get("stable_for", 5.0)),
            poll_interval=float(g.get("poll_interval", 1.0)),
            max_wait=float(g.get("max_wait", 0)),
            on_conflict=g.get("on_conflict", "rename"),
            rename_template=g.get("rename_template", "{stem}_{n}{suffix}"),
            log_level=g.get("log_level", "INFO"),
            log_file="",
            dry_run=False,
            ignore_extensions=tuple(g.get("ignore_extensions", [])),
            ignore_patterns=tuple(g.get("ignore_patterns", [])),
        )

    # ── Lifecycle ──────────────────────────────────────────────────

    def start(self, cfg: Config) -> None:
        """Start watching in background threads."""
        if self._running:
            log.warning("Watcher already running — stop first.")
            return

        self._stop_event.clear()

        configure_logging(level=cfg.log_level)

        # Ensure destination directories exist
        for route in cfg.routes:
            Path(route.destination).mkdir(parents=True, exist_ok=True)

        self._checker = StabilityChecker(cfg, self._stop_event)
        handler = FileWatchHandler(self._checker)

        try:
            self._observer = start_observer(cfg.source, handler)
        except OSError as exc:
            log.error("Failed to start observer: %s", exc)
            self._set_status("error")
            raise

        self._checker.start()
        self._running = True
        self._set_status("watching")
        log.info("GUI watcher started — watching %s", cfg.source)

    def stop(self) -> None:
        """Stop watching gracefully."""
        if not self._running:
            return

        log.info("Stopping watcher…")
        self._stop_event.set()

        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=3)
            self._observer = None

        if self._checker:
            self._checker.join(timeout=5)
            self._checker = None

        self._running = False
        self._set_status("idle")
        log.info("Watcher stopped.")
