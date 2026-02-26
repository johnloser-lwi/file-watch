"""Logging configuration: console + optional rotating file handler."""

from __future__ import annotations

import logging
import logging.handlers
from typing import Optional


def configure_logging(
    level: str = "INFO",
    log_file: str = "",
    log_max_bytes: int = 10_485_760,
    log_backup_count: int = 3,
) -> None:
    """Set up root logger with console handler and optional rotating file handler."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt=datefmt)

    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates on re-init
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setLevel(numeric_level)
    console.setFormatter(formatter)
    root.addHandler(console)

    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=log_max_bytes,
            backupCount=log_backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
