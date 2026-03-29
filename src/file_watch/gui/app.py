"""FileWatch GUI — main application window.

Launch with ``file-watch gui`` or ``python -m file_watch.gui.app``.
"""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

import ttkbootstrap as ttk  # type: ignore
from ttkbootstrap.constants import *  # type: ignore

from file_watch.gui.entry_panel import EntryPanel
from file_watch.gui.presets import IGNORE_PRESETS
from file_watch.gui.settings_io import (
    export_settings,
    import_settings,
    load_settings,
    new_entry,
    save_settings,
)
from file_watch.gui.watcher_bridge import WatcherBridge
from file_watch.gui.widgets import ScrollableFrame, StatusLight

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  Main Application
# ═══════════════════════════════════════════════════════════════════════

class FileWatchApp:
    """Top-level GUI controller."""

    def __init__(self) -> None:
        self._settings = load_settings()
        self._bridge = WatcherBridge()

        # ── Window ──────────────────────────────────────────────────
        win_cfg = self._settings.get("window", {})
        self._root = ttk.Window(
            title="FileWatch",
            themename="darkly",
            size=(win_cfg.get("width", 960), win_cfg.get("height", 720)),
            minsize=(780, 520),
        )
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── Build UI ────────────────────────────────────────────────
        self._build_header()
        self._build_toolbar()
        self._build_entries_area()
        self._build_global_settings_panel()
        self._build_status_bar()

        # ── Load saved entries ──────────────────────────────────────
        self._entry_panels: list[EntryPanel] = []
        entries = self._settings.get("entries", [])
        if not entries:
            entries = [new_entry()]
        for entry_data in entries:
            self._add_entry_panel(entry_data)

        # Bridge status callback
        self._bridge.set_status_callback(self._update_status_from_thread)

    # ── Header ──────────────────────────────────────────────────────

    def _build_header(self) -> None:
        header = ttk.Frame(self._root, padding=(16, 12))
        header.pack(fill=X)

        # Title
        title_frame = ttk.Frame(header)
        title_frame.pack(side=LEFT)

        ttk.Label(
            title_frame, text="⚡ FileWatch",
            font=("Segoe UI", 20, "bold"),
            bootstyle="primary",  # type: ignore
        ).pack(side=LEFT)

        ttk.Label(
            title_frame, text="  ·  File Monitor & Organizer",
            font=("Segoe UI", 11),
            bootstyle="secondary",  # type: ignore
        ).pack(side=LEFT, padx=(4, 0), pady=(6, 0))

        # Status light
        self._status_light = StatusLight(header, initial="idle")
        self._status_light.pack(side=RIGHT, padx=(12, 0))

    # ── Toolbar ─────────────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self._root, padding=(16, 0, 16, 8))
        toolbar.pack(fill=X)

        # Left side — entry management
        left = ttk.Frame(toolbar)
        left.pack(side=LEFT)

        ttk.Button(
            left, text="＋ Add Entry", bootstyle="success",  # type: ignore
            command=self._add_new_entry, width=14,
        ).pack(side=LEFT, padx=(0, 6))

        sep = ttk.Separator(toolbar, orient=VERTICAL)
        sep.pack(side=LEFT, fill=Y, padx=8, pady=2)

        # Center — watcher controls
        center = ttk.Frame(toolbar)
        center.pack(side=LEFT)

        self._start_btn = ttk.Button(
            center, text="▶  Start Watching", bootstyle="primary",  # type: ignore
            command=self._start_watching, width=18,
        )
        self._start_btn.pack(side=LEFT, padx=(0, 6))

        self._stop_btn = ttk.Button(
            center, text="⏹  Stop", bootstyle="danger",  # type: ignore
            command=self._stop_watching, width=10, state=DISABLED,
        )
        self._stop_btn.pack(side=LEFT, padx=(0, 6))

        # Right side — import / export
        right = ttk.Frame(toolbar)
        right.pack(side=RIGHT)

        ttk.Button(
            right, text="📥 Import", bootstyle="secondary-outline",  # type: ignore
            command=self._import_settings, width=10,
        ).pack(side=LEFT, padx=2)

        ttk.Button(
            right, text="📤 Export", bootstyle="secondary-outline",  # type: ignore
            command=self._export_settings, width=10,
        ).pack(side=LEFT, padx=2)

    # ── Entries Area ────────────────────────────────────────────────

    def _build_entries_area(self) -> None:
        self._scroll_frame = ScrollableFrame(self._root, padding=0)
        self._scroll_frame.pack(fill=BOTH, expand=True, padx=16, pady=(0, 4))

    # ── Global Settings Panel ───────────────────────────────────────

    def _build_global_settings_panel(self) -> None:
        g = self._settings.get("global", {})

        panel = ttk.Labelframe(
            self._root, text="  ⚙ Global Settings  ",
            bootstyle="secondary",  # type: ignore
            padding=10,
        )
        panel.pack(fill=X, padx=16, pady=(0, 4))

        # Row 1: timing settings
        row1 = ttk.Frame(panel)
        row1.pack(fill=X, pady=(0, 6))

        # Stable For
        ttk.Label(row1, text="Stable For (s):", width=14, anchor="e").pack(side=LEFT, padx=(0, 4))
        self._stable_var = tk.StringVar(value=str(g.get("stable_for", 5.0)))
        ttk.Entry(row1, textvariable=self._stable_var, width=8).pack(side=LEFT, padx=(0, 16))

        # Poll Interval
        ttk.Label(row1, text="Poll Interval (s):", anchor="e").pack(side=LEFT, padx=(0, 4))
        self._poll_var = tk.StringVar(value=str(g.get("poll_interval", 1.0)))
        ttk.Entry(row1, textvariable=self._poll_var, width=8).pack(side=LEFT, padx=(0, 16))

        # Max Wait
        ttk.Label(row1, text="Max Wait (s):", anchor="e").pack(side=LEFT, padx=(0, 4))
        self._maxwait_var = tk.StringVar(value=str(g.get("max_wait", 0)))
        ttk.Entry(row1, textvariable=self._maxwait_var, width=8).pack(side=LEFT, padx=(0, 16))

        # Conflict
        ttk.Label(row1, text="On Conflict:", anchor="e").pack(side=LEFT, padx=(0, 4))
        self._conflict_var = tk.StringVar(value=g.get("on_conflict", "rename"))
        conflict_combo = ttk.Combobox(
            row1, textvariable=self._conflict_var,
            values=["skip", "overwrite", "rename"],
            state="readonly", width=10,
        )
        conflict_combo.pack(side=LEFT)

        # Row 2: ignore settings
        row2 = ttk.Frame(panel)
        row2.pack(fill=X, pady=(0, 6))

        ttk.Label(row2, text="Ignore Ext:", width=14, anchor="e").pack(side=LEFT, padx=(0, 4))
        self._ignore_ext_var = tk.StringVar(
            value=", ".join(g.get("ignore_extensions", []))
        )
        ttk.Entry(row2, textvariable=self._ignore_ext_var, width=40).pack(side=LEFT, fill=X, expand=True, padx=(0, 16))

        ttk.Label(row2, text="Ignore Patterns:", anchor="e").pack(side=LEFT, padx=(0, 4))
        self._ignore_pat_var = tk.StringVar(
            value=", ".join(g.get("ignore_patterns", []))
        )
        ttk.Entry(row2, textvariable=self._ignore_pat_var, width=40).pack(side=LEFT, fill=X, expand=True)

        # Row 3: ignore preset buttons
        row3 = ttk.Frame(panel)
        row3.pack(fill=X)

        ttk.Label(row3, text="Quick Ignore:", width=14, anchor="e").pack(side=LEFT, padx=(0, 4))

        current_exts = set(self._parse_ignore_extensions())
        current_pats = set(self._parse_ignore_patterns())

        self._ignore_preset_active: set[str] = set()
        self._ignore_preset_buttons: dict[str, ttk.Button] = {}

        for key, preset in IGNORE_PRESETS.items():
            preset_exts = set(preset.get("extensions", []))
            preset_pats = set(preset.get("patterns", []))
            is_active = preset_exts.issubset(current_exts) and preset_pats.issubset(current_pats)
            if is_active:
                self._ignore_preset_active.add(key)

            style = "warning" if is_active else "warning-outline"
            btn = ttk.Button(
                row3,
                text=preset["label"],
                bootstyle=style,  # type: ignore
                command=lambda k=key: self._toggle_ignore_preset(k),
                width=16,
            )
            btn.pack(side=LEFT, padx=2, pady=2)
            self._ignore_preset_buttons[key] = btn

    # ── Status Bar ──────────────────────────────────────────────────

    def _build_status_bar(self) -> None:
        bar = ttk.Frame(self._root, padding=(16, 6))
        bar.pack(fill=X, side=BOTTOM)

        self._status_label = ttk.Label(
            bar, text="Ready — add entries and press Start Watching",
            font=("Segoe UI", 9), bootstyle="secondary",  # type: ignore
        )
        self._status_label.pack(side=LEFT)

        ttk.Label(
            bar, text="Settings: ~/FileWatch/settings.json",
            font=("Segoe UI", 9), bootstyle="secondary",  # type: ignore
        ).pack(side=RIGHT)

    # ═══════════════════════════════════════════════════════════════
    #  Actions
    # ═══════════════════════════════════════════════════════════════

    def _add_entry_panel(self, data: dict[str, Any]) -> None:
        idx = len(self._entry_panels)
        panel = EntryPanel(
            self._scroll_frame.inner,
            data,
            index=idx,
            on_remove=self._remove_entry,
            on_change=self._on_entry_change,
        )
        panel.pack(fill=X, padx=4, pady=4)
        self._entry_panels.append(panel)

    def _add_new_entry(self) -> None:
        self._add_entry_panel(new_entry())
        self._auto_save()

    def _remove_entry(self, panel: EntryPanel) -> None:
        if len(self._entry_panels) <= 1:
            messagebox.showwarning("Cannot Remove", "You need at least one watch entry.")
            return
        if panel.get_data()["source"] or panel.get_data()["destination"]:
            if not messagebox.askyesno("Confirm Remove", "Remove this entry? This cannot be undone."):
                return
        panel.destroy()
        self._entry_panels.remove(panel)
        # Re-index panels
        for i, p in enumerate(self._entry_panels):
            p.set_index(i)
        self._auto_save()

    def _on_entry_change(self) -> None:
        """Called when any entry field changes."""
        self._auto_save()

    # ── Watcher controls ────────────────────────────────────────────

    def _start_watching(self) -> None:
        try:
            cfg = self._build_config()
        except ValueError as exc:
            messagebox.showerror("Configuration Error", str(exc))
            return

        try:
            self._bridge.start(cfg)
        except OSError as exc:
            messagebox.showerror("Watcher Error", str(exc))
            return

        self._start_btn.configure(state=DISABLED)
        self._stop_btn.configure(state=NORMAL)
        self._status_label.configure(text="Watching for new files…")

    def _stop_watching(self) -> None:
        self._bridge.stop()
        self._start_btn.configure(state=NORMAL)
        self._stop_btn.configure(state=DISABLED)
        self._status_label.configure(text="Stopped.")

    def _update_status_from_thread(self, status: str) -> None:
        """Called from the bridge (possibly a non-main thread)."""
        self._root.after(0, lambda: self._status_light.set_status(status))

    # ── Import / Export ─────────────────────────────────────────────

    def _import_settings(self) -> None:
        path = filedialog.askopenfilename(
            title="Import Settings",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            data = import_settings(Path(path))
        except (FileNotFoundError, ValueError) as exc:
            messagebox.showerror("Import Error", str(exc))
            return

        self._settings = data
        self._reload_ui()
        messagebox.showinfo("Import", "Settings imported successfully.")

    def _export_settings(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export Settings",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="filewatch_settings.json",
        )
        if not path:
            return
        self._collect_settings()
        export_settings(self._settings, Path(path))
        messagebox.showinfo("Export", f"Settings exported to:\n{path}")

    # ── Ignore preset toggles ───────────────────────────────────────

    def _toggle_ignore_preset(self, key: str) -> None:
        preset = IGNORE_PRESETS[key]
        p_exts = preset.get("extensions", [])
        p_pats = preset.get("patterns", [])

        cur_exts = self._parse_ignore_extensions()
        cur_pats = self._parse_ignore_patterns()

        if key in self._ignore_preset_active:
            self._ignore_preset_active.discard(key)
            cur_exts = [e for e in cur_exts if e not in p_exts]
            cur_pats = [p for p in cur_pats if p not in p_pats]
            self._ignore_preset_buttons[key].configure(bootstyle="warning-outline")  # type: ignore
        else:
            self._ignore_preset_active.add(key)
            existing_exts = set(cur_exts)
            cur_exts += [e for e in p_exts if e not in existing_exts]
            existing_pats = set(cur_pats)
            cur_pats += [p for p in p_pats if p not in existing_pats]
            self._ignore_preset_buttons[key].configure(bootstyle="warning")  # type: ignore

        self._ignore_ext_var.set(", ".join(cur_exts))
        self._ignore_pat_var.set(", ".join(cur_pats))
        self._auto_save()

    # ── Settings helpers ────────────────────────────────────────────

    def _parse_ignore_extensions(self) -> list[str]:
        raw = self._ignore_ext_var.get()
        return [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]

    def _parse_ignore_patterns(self) -> list[str]:
        raw = self._ignore_pat_var.get()
        return [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]

    def _collect_settings(self) -> None:
        """Gather current UI state into self._settings."""
        self._settings["entries"] = [p.get_data() for p in self._entry_panels]
        self._settings["global"] = {
            "stable_for": float(self._stable_var.get() or 5.0),
            "poll_interval": float(self._poll_var.get() or 1.0),
            "max_wait": float(self._maxwait_var.get() or 0),
            "on_conflict": self._conflict_var.get(),
            "rename_template": "{stem}_{n}{suffix}",
            "ignore_extensions": self._parse_ignore_extensions(),
            "ignore_patterns": self._parse_ignore_patterns(),
        }
        self._settings["window"] = {
            "width": self._root.winfo_width(),
            "height": self._root.winfo_height(),
        }

    def _auto_save(self) -> None:
        """Persist current state to ~/FileWatch/settings.json."""
        try:
            self._collect_settings()
            save_settings(self._settings)
        except Exception as exc:
            log.warning("Auto-save failed: %s", exc)

    def _build_config(self):
        """Build a Config from current UI state."""
        self._collect_settings()
        return WatcherBridge.build_config(
            self._settings["entries"],
            self._settings["global"],
        )

    def _reload_ui(self) -> None:
        """Destroy all panels and rebuild from self._settings."""
        for panel in self._entry_panels:
            panel.destroy()
        self._entry_panels.clear()

        entries = self._settings.get("entries", [new_entry()])
        if not entries:
            entries = [new_entry()]
        for entry_data in entries:
            self._add_entry_panel(entry_data)

        # Reload global settings
        g = self._settings.get("global", {})
        self._stable_var.set(str(g.get("stable_for", 5.0)))
        self._poll_var.set(str(g.get("poll_interval", 1.0)))
        self._maxwait_var.set(str(g.get("max_wait", 0)))
        self._conflict_var.set(g.get("on_conflict", "rename"))
        self._ignore_ext_var.set(", ".join(g.get("ignore_extensions", [])))
        self._ignore_pat_var.set(", ".join(g.get("ignore_patterns", [])))

    def _on_close(self) -> None:
        """Handle window close: stop watcher, save settings, exit."""
        if self._bridge.is_running:
            self._bridge.stop()
        self._auto_save()
        self._root.destroy()

    def run(self) -> None:
        """Start the tkinter mainloop."""
        self._root.mainloop()


# ═══════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    app = FileWatchApp()
    app.run()


if __name__ == "__main__":
    main()
