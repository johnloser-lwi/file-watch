"""Destination conflict resolution strategies."""

from __future__ import annotations

import logging
import time
from pathlib import Path

log = logging.getLogger(__name__)


def resolve_destination(
    src: Path,
    dest_dir: Path,
    on_conflict: str,
    rename_template: str,
) -> Path:
    """Return a destination path for src, applying the chosen conflict strategy.

    Returns the resolved destination Path.

    Raises:
        FileExistsError: with message starting "skip:" when strategy is 'skip'
            and the destination already exists.
        ValueError: for unknown conflict strategy.
    """
    if on_conflict not in ("skip", "overwrite", "rename"):
        raise ValueError(f"Unknown conflict strategy: {on_conflict!r}")

    dest = dest_dir / src.name

    if not dest.exists():
        return dest

    if on_conflict == "skip":
        log.info("Destination exists, skipping: %s", dest)
        raise FileExistsError(f"skip:{dest}")

    if on_conflict == "overwrite":
        log.info("Destination exists, overwriting: %s", dest)
        dest.unlink()
        return dest

    return _rename_resolve(src, dest_dir, rename_template)


def _rename_resolve(src: Path, dest_dir: Path, template: str) -> Path:
    """Find a non-existing destination name using the rename template."""
    stem = src.stem
    suffix = src.suffix

    # Try numbered variants first
    for n in range(1, 10000):
        candidate_name = template.format(stem=stem, suffix=suffix, n=n, ts="")
        # Remove trailing underscores/hyphens that come from empty ts
        candidate_name = candidate_name.replace("_}", "}").replace("{ts}", "")
        # Re-render properly without ts
        candidate_name = _render_template(template, stem=stem, suffix=suffix, n=n, ts=None)
        candidate = dest_dir / candidate_name
        if not candidate.exists():
            log.info("Rename conflict resolved: %s → %s", src.name, candidate_name)
            return candidate

    # Fallback: timestamp-based
    ts = str(int(time.time()))
    candidate_name = _render_template(template, stem=stem, suffix=suffix, n=0, ts=ts)
    candidate = dest_dir / candidate_name
    log.warning("Fell back to timestamp rename: %s → %s", src.name, candidate_name)
    return candidate


def _render_template(template: str, stem: str, suffix: str, n: int, ts: str | None) -> str:
    """Render a rename template, substituting available tokens."""
    ts_val = ts if ts is not None else str(int(time.time()))
    return template.format(stem=stem, suffix=suffix, n=n, ts=ts_val)
