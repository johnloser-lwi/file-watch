"""Tests for conflict resolution strategies."""

from __future__ import annotations

from pathlib import Path

import pytest

from file_watch.conflicts import resolve_destination


class TestResolveDestination:
    def _make_file(self, path: Path, content: str = "data") -> Path:
        path.write_text(content)
        return path

    def test_no_conflict_returns_direct_dest(self, src_dir, dst_dir):
        src = src_dir / "file.txt"
        src.write_text("hello")
        dest = resolve_destination(src, dst_dir, "rename", "{stem}_{n}{suffix}")
        assert dest == dst_dir / "file.txt"

    def test_skip_raises_when_conflict(self, src_dir, dst_dir):
        src = src_dir / "file.txt"
        src.write_text("hello")
        (dst_dir / "file.txt").write_text("existing")
        with pytest.raises(FileExistsError, match="skip:"):
            resolve_destination(src, dst_dir, "skip", "{stem}_{n}{suffix}")

    def test_overwrite_removes_existing(self, src_dir, dst_dir):
        src = src_dir / "file.txt"
        src.write_text("hello")
        existing = dst_dir / "file.txt"
        existing.write_text("existing")
        dest = resolve_destination(src, dst_dir, "overwrite", "{stem}_{n}{suffix}")
        assert dest == dst_dir / "file.txt"
        assert not existing.exists()  # unlinked

    def test_rename_finds_next_available(self, src_dir, dst_dir):
        src = src_dir / "file.txt"
        src.write_text("hello")
        (dst_dir / "file.txt").write_text("existing")
        dest = resolve_destination(src, dst_dir, "rename", "{stem}_{n}{suffix}")
        assert dest == dst_dir / "file_1.txt"

    def test_rename_skips_occupied_slots(self, src_dir, dst_dir):
        src = src_dir / "file.txt"
        src.write_text("hello")
        for name in ["file.txt", "file_1.txt", "file_2.txt"]:
            (dst_dir / name).write_text("existing")
        dest = resolve_destination(src, dst_dir, "rename", "{stem}_{n}{suffix}")
        assert dest == dst_dir / "file_3.txt"

    def test_rename_with_ts_template(self, src_dir, dst_dir):
        src = src_dir / "report.pdf"
        src.write_text("pdf")
        (dst_dir / "report.pdf").write_text("existing")
        dest = resolve_destination(src, dst_dir, "rename", "{stem}_{ts}{suffix}")
        assert dest.parent == dst_dir
        assert dest.suffix == ".pdf"
        assert dest.name != "report.pdf"

    def test_unknown_strategy_raises(self, src_dir, dst_dir):
        src = src_dir / "file.txt"
        src.write_text("hello")
        with pytest.raises(ValueError, match="Unknown conflict"):
            resolve_destination(src, dst_dir, "delete", "{stem}_{n}{suffix}")
