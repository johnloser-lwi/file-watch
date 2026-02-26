"""Tests for StabilityChecker and move logic."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from file_watch.config import Config, Route
from file_watch.mover import StabilityChecker


def _catch_all(dst: str) -> Route:
    return Route(destination=dst, extensions=())


def _route(dst: str, *exts: str) -> Route:
    return Route(destination=dst, extensions=tuple(exts))


def make_cfg(src_dir: Path, dst_dir: Path, **kwargs) -> Config:
    """Build a minimal Config for tests.

    Pass ``routes=`` to override the default single catch-all route.
    Any other Config field can be overridden via kwargs.
    """
    routes = kwargs.pop("routes", (_catch_all(str(dst_dir)),))
    defaults = dict(
        source=str(src_dir),
        routes=routes,
        stable_for=0.3,
        poll_interval=0.1,
        max_wait=0.0,
        on_conflict="rename",
        rename_template="{stem}_{n}{suffix}",
        log_level="DEBUG",
        log_file="",
        log_max_bytes=1_048_576,
        log_backup_count=1,
        dry_run=False,
        ignore_extensions=(),
        ignore_patterns=(),
    )
    defaults.update(kwargs)
    return Config(**defaults)


@pytest.mark.timeout(10)
class TestStabilityChecker:
    def _run_checker(self, cfg: Config) -> tuple[StabilityChecker, threading.Event]:
        stop = threading.Event()
        checker = StabilityChecker(cfg, stop)
        checker.start()
        return checker, stop

    def test_stable_file_is_moved(self, src_dir, dst_dir):
        cfg = make_cfg(src_dir, dst_dir)
        checker, stop = self._run_checker(cfg)

        src_file = src_dir / "hello.txt"
        src_file.write_text("hello world")
        checker.register(str(src_file))

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if (dst_dir / "hello.txt").exists():
                break
            time.sleep(0.05)

        stop.set()
        checker.join(timeout=2)

        assert (dst_dir / "hello.txt").exists()
        assert not src_file.exists()

    def test_file_not_moved_while_growing(self, src_dir, dst_dir):
        cfg = make_cfg(src_dir, dst_dir, stable_for=0.5)
        checker, stop = self._run_checker(cfg)

        src_file = src_dir / "growing.bin"
        src_file.write_bytes(b"a" * 100)
        checker.register(str(src_file))

        start = time.monotonic()
        while time.monotonic() - start < 0.4:
            time.sleep(0.1)
            src_file.write_bytes(src_file.read_bytes() + b"x" * 50)
            checker.register(str(src_file))

        assert src_file.exists(), "File was moved prematurely while still growing"

        stop.set()
        checker.join(timeout=2)

    def test_vanished_file_is_silently_removed(self, src_dir, dst_dir):
        cfg = make_cfg(src_dir, dst_dir)
        checker, stop = self._run_checker(cfg)

        src_file = src_dir / "ghost.txt"
        src_file.write_text("boo")
        checker.register(str(src_file))

        src_file.unlink()

        time.sleep(cfg.stable_for + cfg.poll_interval * 3)
        stop.set()
        checker.join(timeout=2)

        assert not (dst_dir / "ghost.txt").exists()

    def test_dry_run_does_not_move(self, src_dir, dst_dir):
        cfg = make_cfg(src_dir, dst_dir, dry_run=True)
        checker, stop = self._run_checker(cfg)

        src_file = src_dir / "nodry.txt"
        src_file.write_text("content")
        checker.register(str(src_file))

        time.sleep(cfg.stable_for + cfg.poll_interval * 4)
        stop.set()
        checker.join(timeout=2)

        assert src_file.exists(), "File was moved despite dry_run=True"
        assert not (dst_dir / "nodry.txt").exists()

    def test_conflict_rename_applied(self, src_dir, dst_dir):
        cfg = make_cfg(src_dir, dst_dir)
        (dst_dir / "data.txt").write_text("existing")

        checker, stop = self._run_checker(cfg)

        src_file = src_dir / "data.txt"
        src_file.write_text("new content")
        checker.register(str(src_file))

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if (dst_dir / "data_1.txt").exists():
                break
            time.sleep(0.05)

        stop.set()
        checker.join(timeout=2)

        assert (dst_dir / "data_1.txt").exists()

    def test_max_wait_drops_file(self, src_dir, dst_dir):
        cfg = make_cfg(src_dir, dst_dir, stable_for=10.0, max_wait=0.3, poll_interval=0.1)
        checker, stop = self._run_checker(cfg)

        src_file = src_dir / "big.bin"
        src_file.write_bytes(b"x" * 100)
        checker.register(str(src_file))

        start = time.monotonic()
        while time.monotonic() - start < 0.5:
            time.sleep(0.08)
            src_file.write_bytes(src_file.read_bytes() + b"y")
            checker.register(str(src_file))

        stop.set()
        checker.join(timeout=2)

        assert src_file.exists()
        assert not (dst_dir / "big.bin").exists()

    def test_extension_routing(self, src_dir, dst_dir, tmp_path):
        """Files are routed to the correct destination based on extension."""
        img_dir = tmp_path / "images"
        img_dir.mkdir()
        cfg = make_cfg(
            src_dir,
            dst_dir,
            routes=(
                _route(str(img_dir), ".jpg", ".png"),
                _catch_all(str(dst_dir)),
            ),
        )
        checker, stop = self._run_checker(cfg)

        jpg_file = src_dir / "photo.jpg"
        txt_file = src_dir / "notes.txt"
        jpg_file.write_bytes(b"jpeg")
        txt_file.write_text("hello")
        checker.register(str(jpg_file))
        checker.register(str(txt_file))

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if (img_dir / "photo.jpg").exists() and (dst_dir / "notes.txt").exists():
                break
            time.sleep(0.05)

        stop.set()
        checker.join(timeout=2)

        assert (img_dir / "photo.jpg").exists(), "jpg not routed to img_dir"
        assert (dst_dir / "notes.txt").exists(), "txt not routed to catch-all"

    def test_ignored_extension_not_moved(self, src_dir, dst_dir):
        """Files with an ignored extension are never registered."""
        cfg = make_cfg(src_dir, dst_dir, ignore_extensions=(".tmp",))
        checker, stop = self._run_checker(cfg)

        tmp_file = src_dir / "download.tmp"
        tmp_file.write_bytes(b"partial")
        checker.register(str(tmp_file))

        time.sleep(cfg.stable_for + cfg.poll_interval * 4)
        stop.set()
        checker.join(timeout=2)

        assert tmp_file.exists(), "Ignored .tmp file was moved"
        assert not (dst_dir / "download.tmp").exists()

    def test_ignored_pattern_not_moved(self, src_dir, dst_dir):
        """Files matching an ignore glob pattern are never registered."""
        cfg = make_cfg(src_dir, dst_dir, ignore_patterns=("~*",))
        checker, stop = self._run_checker(cfg)

        lock_file = src_dir / "~lockfile"
        lock_file.write_bytes(b"lock")
        checker.register(str(lock_file))

        time.sleep(cfg.stable_for + cfg.poll_interval * 4)
        stop.set()
        checker.join(timeout=2)

        assert lock_file.exists(), "Ignored ~* file was moved"

    def test_no_matching_route_file_skipped(self, src_dir, dst_dir):
        """When routes only cover specific extensions, unmatched files stay."""
        cfg = make_cfg(
            src_dir,
            dst_dir,
            routes=(_route(str(dst_dir), ".pdf"),),
        )
        checker, stop = self._run_checker(cfg)

        txt_file = src_dir / "readme.txt"
        txt_file.write_text("hello")
        checker.register(str(txt_file))

        time.sleep(cfg.stable_for + cfg.poll_interval * 4)
        stop.set()
        checker.join(timeout=2)

        assert txt_file.exists(), ".txt file moved despite no matching route"
