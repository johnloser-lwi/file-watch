"""Reusable themed widgets for the FileWatch GUI."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable, Optional

import ttkbootstrap as ttk  # type: ignore
from ttkbootstrap.constants import *  # type: ignore


class PathPickerRow(ttk.Frame):
    """Label + Entry + Browse button — returns the selected path."""

    def __init__(
        self,
        master: tk.Widget,
        label_text: str,
        variable: tk.StringVar,
        browse_title: str = "Select Folder",
        *,
        entry_width: int = 40,
    ) -> None:
        super().__init__(master)
        self._var = variable

        lbl = ttk.Label(self, text=label_text, width=12, anchor="e")
        lbl.pack(side=LEFT, padx=(0, 6))

        self._entry = ttk.Entry(self, textvariable=variable, width=entry_width)
        self._entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 6))

        btn = ttk.Button(
            self, text="Browse…", bootstyle="outline",  # type: ignore
            command=lambda: self._browse(browse_title),
            width=8,
        )
        btn.pack(side=LEFT)

    def _browse(self, title: str) -> None:
        from tkinter import filedialog
        path = filedialog.askdirectory(title=title)
        if path:
            self._var.set(path)


class PresetButtonBar(ttk.Frame):
    """Row of toggle-style buttons that append/remove preset extensions."""

    def __init__(
        self,
        master: tk.Widget,
        presets: dict[str, dict],
        on_preset_toggle: Callable[[str, bool], None],
        *,
        bootstyle: str = "info-outline",
    ) -> None:
        super().__init__(master)
        self._buttons: dict[str, ttk.Button] = {}
        self._active: set[str] = set()
        self._callback = on_preset_toggle

        for key, preset in presets.items():
            btn = ttk.Button(
                self,
                text=preset["label"],
                bootstyle=bootstyle,  # type: ignore
                command=lambda k=key: self._toggle(k),
                width=14,
            )
            btn.pack(side=LEFT, padx=2, pady=2)
            self._buttons[key] = btn

    def _toggle(self, key: str) -> None:
        if key in self._active:
            self._active.discard(key)
            self._buttons[key].configure(bootstyle="info-outline")  # type: ignore
            self._callback(key, False)
        else:
            self._active.add(key)
            self._buttons[key].configure(bootstyle="info")  # type: ignore
            self._callback(key, True)

    def set_active(self, keys: set[str]) -> None:
        """Programmatically set which presets are active (e.g., on settings load)."""
        for k in list(self._active):
            if k not in keys:
                self._active.discard(k)
                self._buttons[k].configure(bootstyle="info-outline")  # type: ignore
        for k in keys:
            if k in self._buttons:
                self._active.add(k)
                self._buttons[k].configure(bootstyle="info")  # type: ignore


class StatusLight(ttk.Frame):
    """Small colored circle + label to indicate status."""

    _COLORS = {
        "idle": "#6c757d",
        "watching": "#28a745",
        "error": "#dc3545",
    }

    def __init__(self, master: tk.Widget, initial: str = "idle") -> None:
        super().__init__(master)
        self._canvas = tk.Canvas(self, width=14, height=14, highlightthickness=0,
                                  bg=self.winfo_toplevel().cget("bg"))
        self._dot = self._canvas.create_oval(2, 2, 12, 12, fill=self._COLORS[initial], outline="")
        self._canvas.pack(side=LEFT, padx=(0, 4))
        self._label = ttk.Label(self, text=initial.capitalize(), font=("", 9))
        self._label.pack(side=LEFT)

    def set_status(self, status: str) -> None:
        color = self._COLORS.get(status, self._COLORS["idle"])
        self._canvas.itemconfigure(self._dot, fill=color)
        self._label.configure(text=status.capitalize())


class ScrollableFrame(ttk.Frame):
    """A frame that can scroll vertically — used to hold entry cards."""

    def __init__(self, master: tk.Widget, **kw) -> None:
        super().__init__(master, **kw)

        self._canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self._scrollbar = ttk.Scrollbar(self, orient=VERTICAL, command=self._canvas.yview)
        self.inner = ttk.Frame(self._canvas)

        self.inner.bind("<Configure>", lambda _: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas_window = self._canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self._scrollbar.pack(side=RIGHT, fill=Y)

        # Resize inner frame width with canvas
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        # Mouse-wheel scrolling
        self.inner.bind("<Enter>", self._bind_mousewheel)
        self.inner.bind("<Leave>", self._unbind_mousewheel)

    def _on_canvas_resize(self, event: tk.Event) -> None:
        self._canvas.itemconfigure(self._canvas_window, width=event.width)

    def _bind_mousewheel(self, _: tk.Event) -> None:
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind_all("<Button-4>", self._on_mousewheel)
        self._canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self, _: tk.Event) -> None:
        self._canvas.unbind_all("<MouseWheel>")
        self._canvas.unbind_all("<Button-4>")
        self._canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event: tk.Event) -> None:
        if event.num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(1, "units")
        else:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
