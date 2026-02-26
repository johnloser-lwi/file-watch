"""Tests for config loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from file_watch.config import (
    Config, Route, find_route, is_ignored,
    load_config, validate_config, find_config_file,
)


def _route(dst: str, *exts: str) -> Route:
    return Route(destination=dst, extensions=tuple(exts))


def _catch_all(dst: str) -> Route:
    return Route(destination=dst, extensions=())


def make_toml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "file-watch.toml"
    p.write_text(content, encoding="utf-8")
    return p


class TestValidateConfig:
    def test_missing_source_raises(self, dst_dir):
        cfg = Config(source="", routes=(_catch_all(str(dst_dir)),))
        with pytest.raises(ValueError, match="source"):
            validate_config(cfg)

    def test_missing_routes_raises(self, src_dir):
        cfg = Config(source=str(src_dir), routes=())
        with pytest.raises(ValueError, match="route"):
            validate_config(cfg)

    def test_route_empty_destination_raises(self, src_dir):
        cfg = Config(source=str(src_dir), routes=(Route(destination="", extensions=()),))
        with pytest.raises(ValueError, match="empty destination"):
            validate_config(cfg)

    def test_source_equals_destination_raises(self, src_dir):
        cfg = Config(source=str(src_dir), routes=(_catch_all(str(src_dir)),))
        with pytest.raises(ValueError, match="differ"):
            validate_config(cfg)

    def test_non_terminal_catch_all_raises(self, src_dir, dst_dir, tmp_path):
        other = tmp_path / "other"
        other.mkdir()
        cfg = Config(
            source=str(src_dir),
            routes=(
                _catch_all(str(dst_dir)),      # catch-all NOT last
                _route(str(other), ".pdf"),
            ),
        )
        with pytest.raises(ValueError, match="catch-all"):
            validate_config(cfg)

    def test_invalid_on_conflict_raises(self, src_dir, dst_dir):
        cfg = Config(
            source=str(src_dir),
            routes=(_catch_all(str(dst_dir)),),
            on_conflict="delete",
        )
        with pytest.raises(ValueError, match="on_conflict"):
            validate_config(cfg)

    def test_invalid_log_level_raises(self, src_dir, dst_dir):
        cfg = Config(
            source=str(src_dir),
            routes=(_catch_all(str(dst_dir)),),
            log_level="VERBOSE",
        )
        with pytest.raises(ValueError, match="log level"):
            validate_config(cfg)

    def test_rename_template_missing_token_raises(self, src_dir, dst_dir):
        cfg = Config(
            source=str(src_dir),
            routes=(_catch_all(str(dst_dir)),),
            on_conflict="rename",
            rename_template="{stem}{suffix}",
        )
        with pytest.raises(ValueError, match="rename_template"):
            validate_config(cfg)

    def test_valid_config_passes(self, src_dir, dst_dir):
        cfg = Config(source=str(src_dir), routes=(_catch_all(str(dst_dir)),))
        validate_config(cfg)  # should not raise

    def test_negative_stable_for_raises(self, src_dir, dst_dir):
        cfg = Config(
            source=str(src_dir),
            routes=(_catch_all(str(dst_dir)),),
            stable_for=-1.0,
        )
        with pytest.raises(ValueError, match="stable_for"):
            validate_config(cfg)


class TestLoadConfig:
    def test_cli_args_only(self, src_dir, dst_dir):
        cfg = load_config(source=str(src_dir), destination=str(dst_dir))
        assert cfg.source == str(src_dir)
        assert len(cfg.routes) == 1
        assert cfg.routes[0].destination == str(dst_dir)
        assert cfg.routes[0].is_catch_all
        assert cfg.stable_for == 5.0
        assert cfg.on_conflict == "rename"

    def test_toml_routes_loaded(self, src_dir, dst_dir, tmp_path):
        content = f"""
[watch]
source = "{str(src_dir).replace(chr(92), '/')}"
stable_for = 10.0

[[routes]]
destination = "{str(dst_dir).replace(chr(92), '/')}"
extensions = [".pdf", ".docx"]
"""
        toml_path = make_toml(tmp_path, content)
        cfg = load_config(config_path=str(toml_path))
        assert cfg.stable_for == 10.0
        assert len(cfg.routes) == 1
        assert ".pdf" in cfg.routes[0].extensions
        assert ".docx" in cfg.routes[0].extensions

    def test_backward_compat_watch_destination(self, src_dir, dst_dir, tmp_path):
        """[watch].destination without [[routes]] creates an implicit catch-all."""
        content = f"""
[watch]
source = "{str(src_dir).replace(chr(92), '/')}"
destination = "{str(dst_dir).replace(chr(92), '/')}"
"""
        toml_path = make_toml(tmp_path, content)
        cfg = load_config(config_path=str(toml_path))
        assert len(cfg.routes) == 1
        assert cfg.routes[0].is_catch_all
        # Compare as Path objects to be slash-style agnostic on Windows
        assert Path(cfg.routes[0].destination) == dst_dir

    def test_cli_destination_overrides_toml_catchall(self, src_dir, dst_dir, tmp_path):
        """CLI -d replaces any catch-all from the TOML file."""
        other = tmp_path / "other"
        other.mkdir()
        content = f"""
[watch]
source = "{str(src_dir).replace(chr(92), '/')}"
destination = "{str(dst_dir).replace(chr(92), '/')}"
"""
        toml_path = make_toml(tmp_path, content)
        cfg = load_config(config_path=str(toml_path), destination=str(other))
        assert len(cfg.routes) == 1
        assert cfg.routes[0].destination == str(other)

    def test_cli_destination_appended_after_typed_routes(self, src_dir, dst_dir, tmp_path):
        """CLI -d becomes the catch-all after any typed routes in the TOML."""
        content = f"""
[watch]
source = "{str(src_dir).replace(chr(92), '/')}"

[[routes]]
destination = "{str(dst_dir).replace(chr(92), '/')}"
extensions = [".pdf"]
"""
        catchall_dir = tmp_path / "catch"
        catchall_dir.mkdir()
        toml_path = make_toml(tmp_path, content)
        cfg = load_config(config_path=str(toml_path), destination=str(catchall_dir))
        assert len(cfg.routes) == 2
        assert cfg.routes[0].extensions == (".pdf",)
        assert cfg.routes[1].is_catch_all
        assert cfg.routes[1].destination == str(catchall_dir)

    def test_toml_ignore_section(self, src_dir, dst_dir, tmp_path):
        content = f"""
[watch]
source = "{str(src_dir).replace(chr(92), '/')}"
destination = "{str(dst_dir).replace(chr(92), '/')}"

[ignore]
extensions = [".tmp", ".part"]
patterns = ["~*", "*.crdownload"]
"""
        toml_path = make_toml(tmp_path, content)
        cfg = load_config(config_path=str(toml_path))
        assert ".tmp" in cfg.ignore_extensions
        assert ".part" in cfg.ignore_extensions
        assert "~*" in cfg.ignore_patterns
        assert "*.crdownload" in cfg.ignore_patterns

    def test_cli_ignore_args_merged_with_toml(self, src_dir, dst_dir, tmp_path):
        """CLI --ignore-ext values are appended to the TOML ignore list."""
        content = f"""
[watch]
source = "{str(src_dir).replace(chr(92), '/')}"
destination = "{str(dst_dir).replace(chr(92), '/')}"

[ignore]
extensions = [".tmp"]
"""
        toml_path = make_toml(tmp_path, content)
        cfg = load_config(
            config_path=str(toml_path),
            ignore_extensions=[".part"],
            ignore_patterns=["~*"],
        )
        assert ".tmp" in cfg.ignore_extensions
        assert ".part" in cfg.ignore_extensions
        assert "~*" in cfg.ignore_patterns

    def test_missing_explicit_config_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            find_config_file(str(tmp_path / "nonexistent.toml"))

    def test_dry_run_flag(self, src_dir, dst_dir):
        cfg = load_config(source=str(src_dir), destination=str(dst_dir), dry_run=True)
        assert cfg.dry_run is True


class TestFindRoute:
    def test_exact_extension_match(self, dst_dir, tmp_path):
        pdf_dir = tmp_path / "pdf"
        pdf_dir.mkdir()
        routes = (
            _route(str(pdf_dir), ".pdf"),
            _catch_all(str(dst_dir)),
        )
        assert find_route("report.pdf", routes).destination == str(pdf_dir)

    def test_catch_all_fallback(self, dst_dir):
        routes = (
            _route("/dev/null", ".pdf"),
            _catch_all(str(dst_dir)),
        )
        assert find_route("photo.jpg", routes).destination == str(dst_dir)

    def test_no_match_returns_none(self):
        routes = (_route("/dev/null", ".pdf"),)
        assert find_route("photo.jpg", routes) is None

    def test_first_match_wins(self, dst_dir, tmp_path):
        first = tmp_path / "first"
        first.mkdir()
        second = tmp_path / "second"
        second.mkdir()
        routes = (
            _route(str(first), ".pdf"),
            _route(str(second), ".pdf"),
        )
        assert find_route("doc.pdf", routes).destination == str(first)

    def test_case_insensitive_extension(self, dst_dir):
        routes = (_route(str(dst_dir), ".pdf"),)
        assert find_route("DOC.PDF", routes) is not None
        assert find_route("doc.Pdf", routes) is not None


class TestIsIgnored:
    def test_extension_match(self):
        assert is_ignored("file.tmp", (".tmp",), ()) is True

    def test_extension_no_match(self):
        assert is_ignored("file.pdf", (".tmp",), ()) is False

    def test_pattern_match(self):
        assert is_ignored("~lockfile", (), ("~*",)) is True

    def test_pattern_no_match(self):
        assert is_ignored("report.pdf", (), ("~*",)) is False

    def test_extension_normalized(self):
        # Ignore list with dot, file without — still works
        assert is_ignored("file.TMP", (".tmp",), ()) is True
