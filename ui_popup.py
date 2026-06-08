"""
ui_popup.py - Compact CustomTkinter popup for Pinboard.

Design: dark-mode, always-on-top, near-cursor, keyboard-navigable.
Closes on paste, Escape, or click outside.
"""

import threading
import time
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional, List
from datetime import datetime

import customtkinter as ctk
from PIL import Image, ImageTk

from models import ClipEntry
from utils import truncate, format_time_ago, dib_to_png


# ── Appearance ──────────────────────────────────────────────────────────────

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

POPUP_W   = 420
ROW_H     = 56
MAX_ROWS  = 8     # visible rows before scroll
ICON_SIZE = 22

COLOR_BG        = "#1a1a2e"
COLOR_SURFACE   = "#16213e"
COLOR_SURFACE2  = "#0f3460"
COLOR_ACCENT    = "#4a9eff"
COLOR_ACCENT2   = "#7c5cbf"
COLOR_PIN       = "#f5a623"
COLOR_TEXT      = "#e8e8f0"
COLOR_SUBTEXT   = "#8888aa"
COLOR_HOVER     = "#252545"
COLOR_SELECTED  = "#1e3a5f"
COLOR_DANGER    = "#e05555"
FONT_MAIN       = ("Segoe UI", 13)
FONT_SMALL      = ("Segoe UI", 10)
FONT_MONO       = ("Cascadia Code", 11)


class ClipRow(ctk.CTkFrame):
    """
    A single row in the clipboard list.
    Shows: icon | preview text | pin btn | delete btn
    """

    def __init__(
        self,
        master,
        entry: ClipEntry,
        on_paste: Callable[[ClipEntry], None],
        on_pin: Callable[[ClipEntry], None],
        on_delete: Callable[[ClipEntry], None],
        show_thumbnail: bool = True,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.entry = entry
        self._on_paste = on_paste
        self._on_pin = on_pin
        self._on_delete = on_delete
        self._selected = False
        self._thumb_image: Optional[ImageTk.PhotoImage] = None

        self._build(show_thumbnail)
        self._bind_events()

    # ------------------------------------------------------------------ #
    #  Build                                                               #
    # ------------------------------------------------------------------ #

    def _build(self, show_thumbnail: bool) -> None:
        self.configure(
            fg_color=COLOR_SURFACE,
            corner_radius=8,
        )

        # Grid: [icon] [preview] [time] [pin] [del]
        self.grid_columnconfigure(1, weight=1)

        # Left icon / thumbnail
        if self.entry.type == "image" and show_thumbnail and self.entry.image_dib:
            self._add_thumbnail()
        else:
            icon_lbl = ctk.CTkLabel(
                self,
                text=self.entry.type_icon,
                font=("Segoe UI Emoji", ICON_SIZE),
                width=36,
                anchor="center",
            )
            icon_lbl.grid(row=0, column=0, padx=(6, 2), pady=4)

        # Preview text
        preview = truncate(self.entry.display_text, 70)
        self._preview_lbl = ctk.CTkLabel(
            self,
            text=preview,
            font=FONT_MAIN,
            text_color=COLOR_TEXT,
            anchor="w",
            justify="left",
        )
        self._preview_lbl.grid(row=0, column=1, sticky="ew", padx=4, pady=(8, 0))

        # Sub-label: time + use count
        time_str = format_time_ago(self.entry.created_at)
        use_str = f"  ×{self.entry.use_count}" if self.entry.use_count > 0 else ""
        self._sub_lbl = ctk.CTkLabel(
            self,
            text=f"{time_str}{use_str}",
            font=FONT_SMALL,
            text_color=COLOR_SUBTEXT,
            anchor="w",
        )
        self._sub_lbl.grid(row=1, column=1, sticky="w", padx=4, pady=(0, 4))

        # Pin button
        pin_symbol = "📌" if self.entry.pinned else "📍"
        text_color = COLOR_PIN if self.entry.pinned else COLOR_TEXT
        self._pin_btn = ctk.CTkButton(
            self,
            text=pin_symbol,
            text_color=text_color,
            width=28,
            height=28,
            font=("Segoe UI Emoji", 14),
            fg_color="transparent",
            hover_color=COLOR_HOVER,
            command=lambda: self._on_pin(self.entry),
        )
        self._pin_btn.grid(row=0, column=2, padx=2, pady=4, rowspan=2)

        # Delete button
        self._del_btn = ctk.CTkButton(
            self,
            text="✕",
            width=28,
            height=28,
            font=FONT_SMALL,
            fg_color="transparent",
            hover_color=COLOR_DANGER,
            text_color=COLOR_SUBTEXT,
            command=lambda: self._on_delete(self.entry),
        )
        self._del_btn.grid(row=0, column=3, padx=(2, 6), pady=4, rowspan=2)

    def _add_thumbnail(self) -> None:
        try:
            img = dib_to_png(self.entry.image_dib) or Image.open(self.entry.image_path)
            img.thumbnail((48, 36), Image.LANCZOS)
            self._thumb_image = ImageTk.PhotoImage(img)
            lbl = tk.Label(
                self,
                image=self._thumb_image,
                bg=COLOR_SURFACE,
                bd=0,
                cursor="hand2",
            )
            lbl.grid(row=0, column=0, rowspan=2, padx=(6, 2), pady=4)
            lbl.bind("<Button-1>", lambda e: self._on_paste(self.entry))
        except Exception:
            # Fall back to icon
            ctk.CTkLabel(self, text="🖼️", font=("Segoe UI Emoji", ICON_SIZE)).grid(
                row=0, column=0, padx=6, pady=4
            )

    # ------------------------------------------------------------------ #
    #  Selection highlight                                                 #
    # ------------------------------------------------------------------ #

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        if selected:
            self.configure(fg_color=COLOR_SELECTED, border_width=2, border_color=COLOR_SUBTEXT if selected else COLOR_SURFACE)
        else:
            self.configure(fg_color=COLOR_SURFACE, border_width=0)

    # ------------------------------------------------------------------ #
    #  Events                                                              #
    # ------------------------------------------------------------------ #

    def _bind_events(self) -> None:
        for widget in [self, self._preview_lbl, self._sub_lbl]:
            widget.bind("<Button-1>", self._on_click)
            widget.bind("<Double-Button-1>", self._on_dbl_click)
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)

    def _on_click(self, event=None) -> None:
        # Signal popup to select this row
        self.event_generate("<<RowSelected>>", when="now")
        self._on_paste(self.entry)

    def _on_dbl_click(self, event=None) -> None:
        self._on_paste(self.entry)

    def _on_enter(self, event=None) -> None:
        if not self._selected:
            self.configure(fg_color=COLOR_HOVER)

    def _on_leave(self, event=None) -> None:
        if not self._selected:
            self.configure(fg_color=COLOR_SURFACE)


class SectionHeader(ctk.CTkLabel):
    """Thin divider label for 'Pinned' / 'History' sections."""

    def __init__(self, master, text: str, **kwargs):
        super().__init__(
            master,
            text=f"  {text}",
            font=("Segoe UI", 10, "bold"),
            text_color=COLOR_SUBTEXT,
            anchor="w",
            height=20,
            fg_color=COLOR_BG,
            **kwargs,
        )


class PinboardPopup(ctk.CTk):
    """
    Main popup window. Appears near the mouse cursor.
    Always on top, closes on paste or focus-out.
    """

    def __init__(
        self,
        get_clips_fn: Callable[[str], List[ClipEntry]],
        paste_fn: Callable[[ClipEntry], None],
        pin_fn: Callable[[ClipEntry], None],
        delete_fn: Callable[[ClipEntry], None],
        settings,
        open_settings_fn: Callable,
    ):
        super().__init__()

        self._get_clips = get_clips_fn
        self._paste_fn = paste_fn
        self._pin_fn = pin_fn
        self._delete_fn = delete_fn
        self._settings = settings
        self._open_settings_fn = open_settings_fn

        self._clips: List[ClipEntry] = []
        self._rows: List[ClipRow] = []
        self._selected_idx: int = 0
        self._visible = False

        self._setup_window()
        self._build_ui()
        self._bind_keys()
        self.withdraw()  # Start hidden

    # ------------------------------------------------------------------ #
    #  Window setup                                                        #
    # ------------------------------------------------------------------ #

    def _setup_window(self) -> None:
        self.title("Pinboard")
        self.configure(fg_color=COLOR_BG)
        self.overrideredirect(True)   # No title bar
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.97)
        self.after(0, self._apply_tool_window)
        # Round corners on Windows 11
        try:
            import ctypes
            HWND_BROADCAST = 0xFFFF
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            # DWM rounded corners (Windows 11)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                int(self.frame()), 33, ctypes.byref(ctypes.c_int(2)), 4
            )
        except Exception:
            pass
    def _apply_tool_window(self) -> None:
        """
        Set WS_EX_TOOLWINDOW / clear WS_EX_APPWINDOW once at startup.
        Also sets WS_EX_NOACTIVATE so the popup never steals focus from the
        target window — keyboard navigation still works via global hotkey binds.
        Because the window is never withdrawn, this only needs to run once.
        Also applies DWM rounded corners on Windows 11.
        """
        try:
            import ctypes
            GWL_EXSTYLE       = -20
            WS_EX_APPWINDOW   = 0x00040000
            WS_EX_TOOLWINDOW  = 0x00000080
            WS_EX_NOACTIVATE  = 0x08000000  # Prevents popup from stealing focus

            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
 
            # DWM rounded corners (Windows 11, no-op on 10)
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWCP_ROUND = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(DWMWCP_ROUND), ctypes.sizeof(DWMWCP_ROUND),
            )
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  UI build                                                            #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        popup_w = self._settings.get("popup_width", POPUP_W)
        self.geometry(f"{popup_w}x600")   # Height adjusted dynamically

        # ── Search bar ──────────────────────────────────────────────────
        search_frame = ctk.CTkFrame(self, fg_color=COLOR_SURFACE2, corner_radius=10)
        search_frame.pack(fill="x", padx=8, pady=(8, 4))

        search_icon = ctk.CTkLabel(search_frame, text="🔍", font=("Segoe UI Emoji", 14), width=28)
        search_icon.pack(side="left", padx=(8, 0))

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_changed)

        self._search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self._search_var,
            placeholder_text="Search clips…",
            font=FONT_MAIN,
            fg_color="transparent",
            border_width=0,
            height=38,
        )
        self._search_entry.pack(side="left", fill="x", expand=True, padx=4)

        clear_btn = ctk.CTkButton(
            search_frame,
            text="✕",
            width=24,
            font=FONT_SMALL,
            fg_color="transparent",
            hover_color=COLOR_HOVER,
            command=lambda: self._search_var.set(""),
        )
        clear_btn.pack(side="right", padx=4)

        # ── Scrollable clip list ─────────────────────────────────────────
        self._list_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=COLOR_BG,
            scrollbar_button_color=COLOR_SURFACE2,
            scrollbar_button_hover_color=COLOR_ACCENT,
        )
        self._list_frame.pack(fill="both", expand=True, padx=4, pady=2)
        self._list_frame.grid_columnconfigure(0, weight=1)

        # ── Bottom bar ───────────────────────────────────────────────────
        bottom = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, corner_radius=0, height=36)
        bottom.pack(fill="x", side="bottom")

        ctk.CTkLabel(
            bottom,
            text="↑↓ nav  ↵ paste  Del remove  Ctrl+P pin  Esc close",
            font=FONT_SMALL,
            text_color=COLOR_SUBTEXT,
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            bottom,
            text="⚙",
            width=28,
            height=28,
            font=("Segoe UI Emoji", 14),
            fg_color="transparent",
            hover_color=COLOR_HOVER,
            command=self._open_settings_fn,
        ).pack(side="right", padx=6)

    # ------------------------------------------------------------------ #
    #  Show / hide                                                         #
    # ------------------------------------------------------------------ #

    def toggle(self) -> None:
        if self._visible:
            self.hide()
        else:
            self.show()

    def show(self) -> None:
        self._position_near_cursor()
        self._search_var.set("")
        self._refresh_list()
        self.deiconify()
        self.lift()
        self.focus_force()
        self.focus_force()
        self._search_entry.focus_set()
        self._visible = True
        
        #self._selected_idx = 0
        #self.after_idle(lambda: self._list_frame._parent_canvas.yview_moveto(0))

        # Bind focus-out to auto-close
        self.bind("<FocusOut>", self._on_focus_out)

    def hide(self) -> None:
        self.withdraw()
        self._visible = False
        self.unbind("<FocusOut>")

    def _position_near_cursor(self) -> None:
        """Place popup near the mouse, keeping it on-screen."""
        x, y = self.winfo_pointerxy()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = self._settings.get("popup_width", POPUP_W)
        h = min(len(self._clips) * ROW_H + 120, MAX_ROWS * ROW_H + 120)
        h = max(h, 200)

        # Prefer showing above cursor
        cx = min(x + 10, sw - w - 10)
        cy = y - h - 10
        if cy < 10:
            cy = y + 20
        cy = max(10, min(cy, sh - h - 40))

        self.geometry(f"{w}x{h}+{cx}+{cy}")

    def _on_focus_out(self, event=None) -> None:
        # Small delay to allow button clicks to register
        self.after(150, self._check_still_focused)

    def _check_still_focused(self) -> None:
        try:
            focused = self.focus_displayof()
            if focused is None and self._visible:
                self.hide()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  List refresh                                                        #
    # ------------------------------------------------------------------ #

    def refresh(self) -> None:
        """Called externally when clipboard data changes."""
        if self._visible:
            self._refresh_list()

    def _on_search_changed(self, *_) -> None:
        self._refresh_list()

    def _refresh_list(self) -> None:
        query = self._search_var.get().strip()
        
        self._clips = self._get_clips(query)

        # Clear existing rows
        for widget in self._list_frame.winfo_children():
            widget.destroy()
        self._rows.clear()

        # Clamp selection
        self._selected_idx = max(0, min(self._selected_idx, len(self._clips) - 1))

        show_thumbnails = self._settings.get("show_thumbnails", True)

        # Render sections
        pinned = [c for c in self._clips if c.pinned]
        history = [c for c in self._clips if not c.pinned]

        row_idx = 0

        if pinned:
            SectionHeader(self._list_frame, "📌 Pinned entries").grid(
                row=row_idx, column=0, sticky="ew", pady=(2, 0)
            )
            row_idx += 1
            for entry in pinned:
                self._add_row(entry, row_idx, show_thumbnails)
                row_idx += 1

        if history:
            SectionHeader(self._list_frame, "🕐 Clipboard history").grid(
                row=row_idx, column=0, sticky="ew", pady=(6, 0)
            )
            row_idx += 1
            for entry in history:
                self._add_row(entry, row_idx, show_thumbnails)
                row_idx += 1

        if not self._clips:
            ctk.CTkLabel(
                self._list_frame,
                text="No clipboard history yet.\nCopy something to get started!",
                text_color=COLOR_SUBTEXT,
                font=FONT_MAIN,
                justify="center",
            ).grid(row=0, column=0, pady=40)

        self._highlight_selected()

    def _add_row(self, entry: ClipEntry, grid_row: int, show_thumbnails: bool) -> None:
        local_idx = len(self._rows)
        row = ClipRow(
            self._list_frame,
            entry=entry,
            on_paste=self._do_paste,
            on_pin=self._do_pin,
            on_delete=self._do_delete,
            show_thumbnail=show_thumbnails,
        )
        row.grid(row=grid_row, column=0, sticky="ew", padx=4, pady=2)
        row.bind("<<RowSelected>>", lambda e, i=local_idx: self._select(i))
        self._rows.append(row)

    # ------------------------------------------------------------------ #
    #  Selection & keyboard                                                #
    # ------------------------------------------------------------------ #

    def _bind_keys(self) -> None:
        self.bind("<Up>",      self._key_up)
        self.bind("<Down>",    self._key_down)
        self.bind("<Return>",  self._key_enter)
        self.bind("<Delete>",  self._key_delete)
        self.bind("<Escape>",  lambda e: self.hide())
        self.bind("<Control-p>", self._key_ctrl_p)
        # Also bind to search entry
        self._search_entry.bind("<Up>",     self._key_up)
        self._search_entry.bind("<Down>",   self._key_down)
        self._search_entry.bind("<Return>", self._key_enter)
        self._search_entry.bind("<Escape>", lambda e: self.hide())
        self._search_entry.bind("<Delete>", lambda e: None)   # Don't delete from search box

    def _select(self, idx: int) -> None:
        self._selected_idx = idx
        self._highlight_selected()

    def _highlight_selected(self) -> None:
        for i, row in enumerate(self._rows):
            row.set_selected(i == self._selected_idx)

    def _key_up(self, event=None) -> str:
        if self._rows:
            self._selected_idx = max(0, self._selected_idx - 1)
            self._highlight_selected()
            self.after_idle(self._scroll_to_selected)
        return "break"

    def _key_down(self, event=None) -> str:
        if self._rows:
            self._selected_idx = min(len(self._rows) - 1, self._selected_idx + 1)
            self._highlight_selected()
            self.after_idle(self._scroll_to_selected)
        return "break"

    def _key_enter(self, event=None) -> str:
        if self._rows and 0 <= self._selected_idx < len(self._clips):
            self._do_paste(self._clips[self._selected_idx])
        return "break"

    def _key_delete(self, event=None) -> str:
        if self._rows and 0 <= self._selected_idx < len(self._clips):
            self._do_delete(self._clips[self._selected_idx])
        return "break"

    def _key_ctrl_p(self, event=None) -> str:
        if self._rows and 0 <= self._selected_idx < len(self._clips):
            self._do_pin(self._clips[self._selected_idx])
        return "break"

    def _scroll_to_selected(self) -> None:
        if not (0 <= self._selected_idx < len(self._rows)):
            return

        try:
            canvas = self._list_frame._parent_canvas
            row = self._rows[self._selected_idx]

            canvas.update_idletasks()

            # Position of widget inside scroll frame
            widget_y = row.winfo_y()
            widget_h = row.winfo_height()

            # Visible region in canvas coordinates
            view_top = canvas.canvasy(0)
            view_bottom = view_top + canvas.winfo_height()

            margin = 20

            # Scroll up if above visible area
            if widget_y < view_top + margin:
                canvas.yview_moveto(max(0, (widget_y - margin) / self._get_scroll_height(canvas)))

            # Scroll down if below visible area
            elif widget_y + widget_h > view_bottom - margin:
                canvas.yview_moveto(
                    max(
                        0,
                        (widget_y + widget_h - canvas.winfo_height() + margin)
                        / self._get_scroll_height(canvas),
                    )
                )

        except Exception:
            pass

    def _get_scroll_height(self, canvas) -> int:
        try:
            bbox = canvas.bbox("all")
            return bbox[3] if bbox else 1
        except Exception:
            return 1

    # ------------------------------------------------------------------ #
    #  Actions                                                             #
    # ------------------------------------------------------------------ #

    def _do_paste(self, entry: ClipEntry) -> None:
        self.hide()
        # Small delay so target window regains focus
        self.after(80, lambda: self._paste_fn(entry))

    def _do_pin(self, entry: ClipEntry) -> None:
        self._pin_fn(entry)
        self._refresh_list()

    def _do_delete(self, entry: ClipEntry) -> None:
        self._delete_fn(entry)
        self._selected_idx = max(0, self._selected_idx - 1)
        self._refresh_list()


class SettingsDialog(ctk.CTkToplevel):
    """Simple modal settings window."""

    def __init__(self, parent, settings, on_save: Callable):
        super().__init__(parent)
        self.title("Pinboard Settings")
        self.geometry("380x440")
        self.configure(fg_color=COLOR_BG)
        self.attributes("-topmost", True)
        self.grab_set()

        self._settings = settings
        self._on_save = on_save
        self._vars: dict = {}

        self._build()

    def _build(self) -> None:
        pad = {"padx": 20}#, "pady": 6}

        ctk.CTkLabel(self, text="⚙ Settings", font=("Segoe UI", 16, "bold")).pack(**pad, pady=(16, 4))

        fields = [
            ("Max History Size", "max_history", "int"),
            ("Popup Width (px)", "popup_width", "int"),
            ("Global Hotkey", "hotkey", "str"),
        ]

        for label, key, typ in fields:
            frame = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, corner_radius=8)
            frame.pack(fill="x", **pad)
            ctk.CTkLabel(frame, text=label, font=FONT_MAIN, anchor="w").pack(side="left", padx=10, pady=8)
            var = tk.StringVar(value=str(self._settings.get(key, "")))
            self._vars[key] = (var, typ)
            ctk.CTkEntry(frame, textvariable=var, width=120, font=FONT_MAIN).pack(side="right", padx=10, pady=8)

        toggles = [
            ("Show Thumbnails", "show_thumbnails"),
            ("Start with Windows", "startup_with_windows"),
        ]
        for label, key in toggles:
            var = tk.BooleanVar(value=bool(self._settings.get(key, False)))
            self._vars[key] = (var, "bool")
            switch = ctk.CTkSwitch(self, text=label, variable=var, font=FONT_MAIN)
            switch.pack(**pad, anchor="w")

        ctk.CTkButton(
            self,
            text="Save Settings",
            command=self._save,
            fg_color=COLOR_ACCENT,
            font=FONT_MAIN,
            height=38,
            corner_radius=8,
        ).pack(fill="x", padx=20, pady=(16, 8))

    def _save(self) -> None:
        updates = {}
        for key, (var, typ) in self._vars.items():
            val = var.get()
            if typ == "int":
                try:
                    updates[key] = int(val)
                except ValueError:
                    pass
            elif typ == "bool":
                updates[key] = bool(val)
            else:
                updates[key] = str(val)
        self._on_save(updates)
        self.destroy()
