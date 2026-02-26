"""Tests for CLI commands."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from file_watch.cli import main
from file_watch import __version__


@pytest.fixture
def runner():
    return CliRunner()


class TestVersionCommand:
    def test_version_output(self, runner):
        result = runner.invoke(main, ["version"])
        assert result.exit_code == 0
        assert __version__ in result.output


class TestConfigPathCommand:
    def test_no_config_found_exits_nonzero(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["config-path"])
        assert result.exit_code != 0

    def test_explicit_missing_config_exits_nonzero(self, runner, tmp_path):
        result = runner.invoke(main, ["--config", str(tmp_path / "missing.toml"), "config-path"])
        assert result.exit_code != 0

    def test_explicit_existing_config_printed(self, runner, tmp_path):
        cfg_file = tmp_path / "my.toml"
        cfg_file.write_text("[watch]\nsource='/a'\n\n[[routes]]\ndestination='/b'\n")
        result = runner.invoke(main, ["--config", str(cfg_file), "config-path"])
        assert result.exit_code == 0
        assert str(cfg_file.resolve()) in result.output


class TestStartCommand:
    def test_missing_source_and_dest_exits_error(self, runner):
        result = runner.invoke(main, ["start"])
        assert result.exit_code != 0

    def test_source_equals_dest_exits_error(self, runner, tmp_path):
        d = tmp_path / "same"
        d.mkdir()
        result = runner.invoke(main, ["start", "-s", str(d), "-d", str(d)])
        assert result.exit_code != 0

    def test_invalid_conflict_strategy_exits_error(self, runner, src_dir, dst_dir):
        result = runner.invoke(
            main,
            ["start", "-s", str(src_dir), "-d", str(dst_dir), "--on-conflict", "invalid"],
        )
        assert result.exit_code != 0

    def test_help_shows_options(self, runner):
        result = runner.invoke(main, ["start", "--help"])
        assert result.exit_code == 0
        assert "--source" in result.output or "-s" in result.output
        assert "--destination" in result.output or "-d" in result.output
        assert "--stable-for" in result.output
        assert "--dry-run" in result.output
        assert "--ignore-ext" in result.output
        assert "--ignore-pattern" in result.output

    def test_ignore_ext_option_accepted(self, src_dir, dst_dir):
        """--ignore-ext and --ignore-pattern are accepted and normalised by load_config."""
        from file_watch.config import load_config
        cfg = load_config(
            source=str(src_dir),
            destination=str(dst_dir),
            ignore_extensions=[".tmp", "part"],   # with and without leading dot
            ignore_patterns=["~*", "*.crdownload"],
        )
        assert ".tmp" in cfg.ignore_extensions
        assert ".part" in cfg.ignore_extensions   # normalised
        assert "~*" in cfg.ignore_patterns
        assert "*.crdownload" in cfg.ignore_patterns
