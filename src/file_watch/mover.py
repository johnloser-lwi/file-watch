"""Stability checker thread and file move logic."""

from __future__ import annotations

import logging
import os
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from file_watch.config import Config, find_route, is_ignored
from file_watch.conflicts import resolve_destination

log = logging.getLogger(__name__)

_MOVE_RETRY_COUNT = 3
_MOVE_RETRY_DELAY = 2.0  # seconds


@dataclass
class PendingFile:
    path: str
    last_size: int
    last_mtime: float
    size_stable_since: float  # time.monotonic() when size last changed
    first_seen: float         # time.monotonic() when first registered


class StabilityChecker(threading.Thread):
    """Daemon thread that polls pending files and moves stable ones."""

    def __init__(self, cfg: Config, stop_event: threading.Event) -> None:
        super().__init__(name="StabilityChecker", daemon=True)
        self._cfg = cfg
        self._stop_event = stop_event
        self._lock = threading.Lock()
        self._pending: Dict[str, PendingFile] = {}

    def register(self, path: str) -> None:
        """Add or refresh a file in the pending dict.

        Silently drops files that match an ignore rule or have no matching route.
        """
        if is_ignored(path, self._cfg.ignore_extensions, self._cfg.ignore_patterns):
            log.debug("Ignored (rule match): %s", path)
            return

        if find_route(path, self._cfg.routes) is None:
            log.debug("No matching route, ignoring: %s", path)
            return

        now = time.monotonic()
        try:
            stat = os.stat(path)
        except OSError:
            log.debug("Cannot stat newly registered file, skipping: %s", path)
            return

        with self._lock:
            if path in self._pending:
                entry = self._pending[path]
                if stat.st_size != entry.last_size or stat.st_mtime != entry.last_mtime:
                    entry.last_size = stat.st_size
                    entry.last_mtime = stat.st_mtime
                    entry.size_stable_since = now
            else:
                self._pending[path] = PendingFile(
                    path=path,
                    last_size=stat.st_size,
                    last_mtime=stat.st_mtime,
                    size_stable_since=now,
                    first_seen=now,
                )
                log.debug("Registered pending file: %s (%d bytes)", path, stat.st_size)

    def run(self) -> None:
        log.debug("StabilityChecker started (poll_interval=%.1fs)", self._cfg.poll_interval)
        while not self._stop_event.wait(timeout=self._cfg.poll_interval):
            self._poll_once()
        # Final poll on shutdown to catch any last stable files
        self._poll_once()
        log.debug("StabilityChecker stopped")

    def _poll_once(self) -> None:
        now = time.monotonic()
        to_remove: list[str] = []

        with self._lock:
            snapshot = list(self._pending.items())

        for path, entry in snapshot:
            try:
                stat = os.stat(path)
            except FileNotFoundError:
                log.debug("File vanished: %s", path)
                to_remove.append(path)
                continue
            except OSError as exc:
                log.warning("Cannot stat %s: %s — retrying next poll", path, exc)
                continue

            size_changed = stat.st_size != entry.last_size
            mtime_changed = stat.st_mtime != entry.last_mtime

            if size_changed or mtime_changed:
                entry.last_size = stat.st_size
                entry.last_mtime = stat.st_mtime
                entry.size_stable_since = now

                if self._cfg.max_wait > 0 and (now - entry.first_seen) > self._cfg.max_wait:
                    log.warning(
                        "max_wait (%.1fs) exceeded for %s — dropping", self._cfg.max_wait, path
                    )
                    to_remove.append(path)
                continue

            # Size and mtime unchanged — check stability window
            if (now - entry.size_stable_since) >= self._cfg.stable_for:
                log.info("Stable, processing: %s (%d bytes)", path, stat.st_size)
                to_remove.append(path)
                self._move_file(path)

        with self._lock:
            for p in to_remove:
                self._pending.pop(p, None)

    def _move_file(self, path: str) -> None:
        src = Path(path)

        route = find_route(path, self._cfg.routes)
        if route is None:
            log.debug("No matching route for %s at move time — skipping", path)
            return

        dest_dir = Path(route.destination)
        operation = getattr(route, 'operation', 'move')

        try:
            dest = resolve_destination(
                src,
                dest_dir,
                self._cfg.on_conflict,
                self._cfg.rename_template,
            )
        except FileExistsError as exc:
            if str(exc).startswith("skip:"):
                log.info("Skipped (conflict): %s", path)
            else:
                log.error("Conflict resolution error for %s: %s", path, exc)
            return

        if self._cfg.dry_run:
            verb = "copy" if operation == "copy" else "move"
            log.info("[DRY RUN] Would %s: %s → %s", verb, path, dest)
            return

        self._do_transfer(src, dest, operation)

    def _do_transfer(self, src: Path, dest: Path, operation: str = "move") -> None:
        verb = "Copying" if operation == "copy" else "Moving"
        past = "Copied" if operation == "copy" else "Moved"
        for attempt in range(1, _MOVE_RETRY_COUNT + 1):
            try:
                if operation == "copy":
                    shutil.copy2(str(src), str(dest))
                else:
                    shutil.move(str(src), str(dest))
                log.info("%s: %s → %s", past, src, dest)
                return
            except PermissionError as exc:
                if attempt < _MOVE_RETRY_COUNT:
                    log.warning(
                        "PermissionError %s %s (attempt %d/%d): %s — retrying in %.1fs",
                        verb.lower(), src, attempt, _MOVE_RETRY_COUNT, exc, _MOVE_RETRY_DELAY,
                    )
                    time.sleep(_MOVE_RETRY_DELAY)
                else:
                    log.error(
                        "Failed to %s %s after %d attempts: %s",
                        operation, src, _MOVE_RETRY_COUNT, exc,
                    )
            except OSError as exc:
                log.error("Error %s %s → %s: %s", verb.lower(), src, dest, exc)
                return
