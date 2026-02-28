"""Click CLI: commands, flags, and watcher lifecycle."""

from __future__ import annotations

import logging
import signal
import sys
import threading
from pathlib import Path

import click

from file_watch import __version__
from file_watch.config import find_config_file, load_config
from file_watch.logging_setup import configure_logging
from file_watch.mover import StabilityChecker
from file_watch.watcher import FileWatchHandler, start_observer

log = logging.getLogger(__name__)


@click.group()
@click.option("--config", "config_path", metavar="PATH", default=None, help="Path to config file.")
@click.option(
    "--log-level",
    default=None,
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    help="Override log level.",
)
@click.pass_context
def main(ctx: click.Context, config_path: str | None, log_level: str | None) -> None:
    """file-watch: Monitor a folder and move stable files to a destination."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path
    ctx.obj["log_level"] = log_level


@main.command()
def version() -> None:
    """Print version and exit."""
    click.echo(f"file-watch {__version__}")


@main.command(name="config-path")
@click.pass_context
def config_path_cmd(ctx: click.Context) -> None:
    """Print resolved config file path and exit."""
    explicit = ctx.obj.get("config_path")
    try:
        found = find_config_file(explicit)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if found:
        click.echo(str(found.resolve()))
    else:
        click.echo("No config file found.", err=True)
        sys.exit(1)


@main.command()
@click.option("-s", "--source", default=None, metavar="PATH", help="Source directory to watch.")
@click.option(
    "-d", "--destination", default=None, metavar="PATH",
    help="Catch-all destination directory. For type-based routing use a config file.",
)
@click.option("--stable-for", default=None, type=float, help="Seconds of stability before move (default: 5.0).")
@click.option("--poll-interval", default=None, type=float, help="Polling interval in seconds (default: 1.0).")
@click.option("--max-wait", default=None, type=float, help="Max seconds to track a file (0=forever, default: 0).")
@click.option(
    "--on-conflict",
    default=None,
    type=click.Choice(["skip", "overwrite", "rename"], case_sensitive=False),
    help="Conflict resolution strategy (default: rename).",
)
@click.option("--rename-template", default=None, help="Template for renamed files.")
@click.option("--log-file", default=None, metavar="PATH", help="Write logs to this file.")
@click.option("--dry-run", is_flag=True, default=False, help="Log moves without executing them.")
@click.option(
    "--ignore-ext", "ignore_extensions", multiple=True, metavar="EXT",
    help="File extension to ignore, e.g. .tmp (repeatable).",
)
@click.option(
    "--ignore-pattern", "ignore_patterns", multiple=True, metavar="PATTERN",
    help="Glob filename pattern to ignore, e.g. '~*' (repeatable).",
)
@click.pass_context
def start(
    ctx: click.Context,
    source: str | None,
    destination: str | None,
    stable_for: float | None,
    poll_interval: float | None,
    max_wait: float | None,
    on_conflict: str | None,
    rename_template: str | None,
    log_file: str | None,
    dry_run: bool,
    ignore_extensions: tuple,
    ignore_patterns: tuple,
) -> None:
    """Watch source and move stable files to destination.

    For type-based routing (different destinations per file type) and ignore
    rules, use a config file. See config.example.toml for the full format.
    """
    config_path = ctx.obj.get("config_path")
    cli_log_level = ctx.obj.get("log_level")

    try:
        cfg = load_config(
            config_path=config_path,
            source=source,
            destination=destination,
            stable_for=stable_for,
            poll_interval=poll_interval,
            max_wait=max_wait,
            on_conflict=on_conflict,
            rename_template=rename_template,
            log_level=cli_log_level,
            log_file=log_file,
            dry_run=dry_run,
            ignore_extensions=ignore_extensions,
            ignore_patterns=ignore_patterns,
        )
    except (ValueError, FileNotFoundError) as exc:
        click.echo(f"Configuration error: {exc}", err=True)
        sys.exit(1)

    configure_logging(
        level=cfg.log_level,
        log_file=cfg.log_file,
        log_max_bytes=cfg.log_max_bytes,
        log_backup_count=cfg.log_backup_count,
    )

    # Ensure all route destination directories exist
    for route in cfg.routes:
        Path(route.destination).mkdir(parents=True, exist_ok=True)

    if cfg.dry_run:
        log.info("DRY RUN mode — no files will be moved")

    log.info(
        "Watching: %s  (stable_for=%.1fs, poll=%.1fs, conflict=%s%s)",
        cfg.source,
        cfg.stable_for,
        cfg.poll_interval,
        cfg.on_conflict,
        ", DRY RUN" if cfg.dry_run else "",
    )
    for route in cfg.routes:
        exts = ", ".join(sorted(route.extensions)) if route.extensions else "(catch-all)"
        log.info("  Route [%s] → %s", exts, route.destination)
    if cfg.ignore_extensions or cfg.ignore_patterns:
        log.info(
            "  Ignoring: extensions=%s  patterns=%s",
            list(cfg.ignore_extensions),
            list(cfg.ignore_patterns),
        )

    run_watcher(cfg)


def run_watcher(cfg) -> None:
    """Start the observer and stability checker; block until SIGINT/SIGTERM."""
    stop_event = threading.Event()

    checker = StabilityChecker(cfg, stop_event)
    handler = FileWatchHandler(checker)

    try:
        observer = start_observer(cfg.source, handler)
    except OSError as exc:
        log.error("Failed to start observer: %s", exc)
        sys.exit(1)

    checker.start()

    def _shutdown(signum=None, frame=None) -> None:
        log.info("Shutdown signal received, stopping...")
        stop_event.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while not stop_event.wait(timeout=0.5):
            pass
    finally:
        observer.stop()
        observer.join()
        checker.join(timeout=cfg.poll_interval * 2 + 1)
        log.info("file-watch stopped.")
