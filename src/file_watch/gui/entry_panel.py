"""Watch-entry card widget — one card per source → destination route."""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable

import ttkbootstrap as ttk  # type: ignore
from ttkbootstrap.constants import *  # type: ignore

from file_watch.gui.presets import EXTENSION_PRESETS
from file_watch.gui.widgets import PathPickerRow


class EntryPanel(ttk.Labelframe):
    """A single watch-entry card with source, destination, operation,
    extension filter, and preset quick-buttons.
    """

    def __init__(
        self,
        master: tk.Widget,
        entry_data: dict[str, Any],
        index: int,
        on_remove: Callable[["EntryPanel"], None],
        on_change: Callable[[], None],
    ) -> None:
        super().__init__(master, text=f"  Entry {index + 1}  ", bootstyle="primary")  # type: ignore
        self._on_remove = on_remove
        self._on_change = on_change
        self._index = index

        self.columnconfigure(1, weight=1)

        # ── Row 0: Source ────────────────────────────────────────────
        self._source_var = tk.StringVar(value=entry_data.get("source", ""))
        source_row = PathPickerRow(
            self, "Source:", self._source_var, browse_title="Select Watch Folder",
            entry_width=50,
        )
        source_row.grid(row=0, column=0, columnspan=3, sticky="ew", padx=8, pady=(8, 2))
        self._source_var.trace_add("write", lambda *_: self._on_change())

        # ── Row 1: Destination ───────────────────────────────────────
        self._dest_var = tk.StringVar(value=entry_data.get("destination", ""))
        dest_row = PathPickerRow(
            self, "Destination:", self._dest_var, browse_title="Select Destination Folder",
            entry_width=50,
        )
        dest_row.grid(row=1, column=0, columnspan=3, sticky="ew", padx=8, pady=2)
        self._dest_var.trace_add("write", lambda *_: self._on_change())

        # ── Row 2: Operation + Enable toggle + Remove ────────────────
        ctrl_frame = ttk.Frame(self)
        ctrl_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=8, pady=2)

        ttk.Label(ctrl_frame, text="Operation:", width=12, anchor="e").pack(side=LEFT, padx=(0, 6))
        self._op_var = tk.StringVar(value=entry_data.get("operation", "move"))
        for val, lbl in [("move", "Move"), ("copy", "Copy")]:
            ttk.Radiobutton(
                ctrl_frame, text=lbl, variable=self._op_var, value=val,
                bootstyle="info-toolbutton",  # type: ignore
                command=self._on_change,
                width=7,
            ).pack(side=LEFT, padx=2)

        # Spacer
        ttk.Frame(ctrl_frame).pack(side=LEFT, fill=X, expand=True)

        # Enable toggle
        self._enabled_var = tk.BooleanVar(value=entry_data.get("enabled", True))
        ttk.Checkbutton(
            ctrl_frame, text="Enabled", variable=self._enabled_var,
            bootstyle="success-round-toggle",  # type: ignore
            command=self._on_change,
        ).pack(side=LEFT, padx=(0, 10))

        # Remove button
        ttk.Button(
            ctrl_frame, text="✕ Remove", bootstyle="danger-outline",  # type: ignore
            command=lambda: self._on_remove(self),
            width=10,
        ).pack(side=LEFT)

        # ── Row 3: Extensions filter ─────────────────────────────────
        ext_frame = ttk.Frame(self)
        ext_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=8, pady=2)

        ttk.Label(ext_frame, text="Extensions:", width=12, anchor="e").pack(side=LEFT, padx=(0, 6))
        self._ext_var = tk.StringVar(
            value=", ".join(entry_data.get("extensions", []))
        )
        ext_entry = ttk.Entry(ext_frame, textvariable=self._ext_var, width=60)
        ext_entry.pack(side=LEFT, fill=X, expand=True)
        self._ext_var.trace_add("write", lambda *_: self._on_change())

        # ── Row 4: Preset quick-buttons ──────────────────────────────
        preset_frame = ttk.Frame(self)
        preset_frame.grid(row=4, column=0, columnspan=3, sticky="ew", padx=8, pady=(2, 8))

        ttk.Label(preset_frame, text="Quick Add:", width=12, anchor="e").pack(side=LEFT, padx=(0, 6))

        # Determine which presets are already active based on current extensions
        current_exts = set(self._parse_extensions())
        self._active_presets: set[str] = set()
        for key, preset in EXTENSION_PRESETS.items():
            if set(preset["extensions"]).issubset(current_exts):
                self._active_presets.add(key)

        self._preset_buttons: dict[str, ttk.Button] = {}
        for key, preset in EXTENSION_PRESETS.items():
            is_active = key in self._active_presets
            style = "info" if is_active else "info-outline"
            btn = ttk.Button(
                preset_frame,
                text=preset["label"],
                bootstyle=style,  # type: ignore
                command=lambda k=key: self._toggle_preset(k),
                width=13,
            )
            btn.pack(side=LEFT, padx=2, pady=2)
            self._preset_buttons[key] = btn

    # ── Data access ─────────────────────────────────────────────────

    def get_data(self) -> dict[str, Any]:
        """Return the entry's current state as a dict."""
        return {
            "source": self._source_var.get().strip(),
            "destination": self._dest_var.get().strip(),
            "operation": self._op_var.get(),
            "extensions": self._parse_extensions(),
            "enabled": self._enabled_var.get(),
        }

    def set_index(self, idx: int) -> None:
        self._index = idx
        self.configure(text=f"  Entry {idx + 1}  ")

    # ── Preset handling ─────────────────────────────────────────────

    def _toggle_preset(self, key: str) -> None:
        preset_exts = EXTENSION_PRESETS[key]["extensions"]
        current = self._parse_extensions()

        if key in self._active_presets:
            # Remove preset extensions
            self._active_presets.discard(key)
            new_exts = [e for e in current if e not in preset_exts]
            self._preset_buttons[key].configure(bootstyle="info-outline")  # type: ignore
        else:
            # Add preset extensions (avoid duplicates)
            self._active_presets.add(key)
            existing = set(current)
            new_exts = current + [e for e in preset_exts if e not in existing]
            self._preset_buttons[key].configure(bootstyle="info")  # type: ignore

        self._ext_var.set(", ".join(new_exts))

    def _parse_extensions(self) -> list[str]:
        """Parse the comma-separated extensions string into a clean list."""
        raw = self._ext_var.get()
        parts = [p.strip().lower() for p in raw.replace(";", ",").split(",") if p.strip()]
        return [p if p.startswith(".") else f".{p}" for p in parts]

    def _refresh_preset_highlights(self) -> None:
        """Re-check which presets are fully present in current extensions."""
        current = set(self._parse_extensions())
        for key, preset in EXTENSION_PRESETS.items():
            if set(preset["extensions"]).issubset(current):
                self._active_presets.add(key)
                self._preset_buttons[key].configure(bootstyle="info")  # type: ignore
            else:
                self._active_presets.discard(key)
                self._preset_buttons[key].configure(bootstyle="info-outline")  # type: ignore
