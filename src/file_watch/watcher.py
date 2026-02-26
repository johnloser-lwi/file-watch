"""Watchdog-based filesystem event handler and observer setup."""

from __future__ import annotations

import logging
from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

log = logging.getLogger(__name__)


class FileWatchHandler(FileSystemEventHandler):
    """Handle filesystem events from watchdog and register files with the mover."""

    def __init__(self, mover: "StabilityChecker") -> None:  # noqa: F821
        super().__init__()
        self._mover = mover

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = str(event.src_path)
        log.debug("File created: %s", path)
        self._mover.register(path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = str(event.src_path)
        log.debug("File modified: %s", path)
        self._mover.register(path)

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        # A file moved into the watch dir — treat destination as new file
        dest_path = str(event.dest_path)
        log.debug("File moved into watch dir: %s", dest_path)
        self._mover.register(dest_path)


def start_observer(source: str, handler: FileWatchHandler) -> Observer:
    """Create, schedule, and start a watchdog Observer for the source directory."""
    observer = Observer()
    observer.schedule(handler, path=source, recursive=False)
    observer.start()
    log.info("Watching: %s", source)
    return observer
