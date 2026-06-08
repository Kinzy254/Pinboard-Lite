"""
main.py - Pinboard clipboard manager entry point.

Orchestrates:
  - ClipboardListener   (background Win32 thread)
  - Database            (SQLite, thread-safe)
  - PinboardPopup       (CustomTkinter main window)
  - TrayIcon            (pystray thread)
  - HotkeyManager       (keyboard library)

Run with: python main.py
"""

import sys
import time
import threading
import ctypes
import ctypes.wintypes

import keyboard   # must import before any GUI init on Windows
import win32api
import win32clipboard
import win32con

from settings import get_settings
from database import Database
from models import ClipEntry
from clipboard_listener import ClipboardListener, set_clipboard_data
from hotkeys import HotkeyManager
from tray import TrayIcon
from ui_popup import PinboardPopup, SettingsDialog


class Pinboard:
    """Main application controller."""

    def __init__(self):
        self._settings = get_settings()
        self._db = Database()
        self._hotkeys = HotkeyManager()
        self._popup: PinboardPopup | None = None
        self._tray: TrayIcon | None = None
        self._listener: ClipboardListener | None = None

    # ------------------------------------------------------------------ #
    #  Startup                                                             #
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        """Start all subsystems and enter the Tkinter event loop."""

        # 1. Clipboard listener (background Win32 window)
        self._listener = ClipboardListener(on_clip=self._on_new_clip)
        self._listener.start()

        # 2. System tray icon (background thread)
        self._tray = TrayIcon(
            on_open=self._show_popup,
            on_pause=self._toggle_pause,
            on_clear_history=self._clear_history,
            on_exit=self._quit,
        )
        self._tray.start()

        # 3. Build the CustomTkinter popup (must be on main thread)
        self._popup = PinboardPopup(
            get_clips_fn=self._db.get_all,
            paste_fn=self._paste_entry,
            pin_fn=lambda e: (self._db.toggle_pin(e.id), self._popup.refresh() if self._popup else None),
            delete_fn=self._delete_entry,
            settings=self._settings,
            open_settings_fn=self._open_settings,
        )

        # 4. Global hotkey
        hotkey = self._settings.get("hotkey", "win+shift+v")
        self._hotkeys.register(
            hotkey,
            callback=self._toggle_popup_from_hotkey,
            name="open_popup",
        )

        # Startup registry
        if self._settings.get("startup_with_windows", False):
            #set_startup_registry(True)
            pass

        print("[Pinboard] Running. Press Win+Shift+V to open.")
        self._popup.mainloop()

    # ------------------------------------------------------------------ #
    #  Clipboard events                                                    #
    # ------------------------------------------------------------------ #

    def _on_new_clip(self, entry: ClipEntry) -> None:
        """Called from the clipboard listener thread when clipboard changes."""
        new_id = self._db.add(entry)
        if new_id is not None:
            entry.id = new_id
            # Schedule UI refresh on the main thread
            if self._popup:
                self._popup.after(0, self._popup.refresh)

    # ------------------------------------------------------------------ #
    #  Popup control                                                       #
    # ------------------------------------------------------------------ #

    def _show_popup(self) -> None:
        """Open popup (safe to call from any thread)."""
        if self._popup:
            self._popup.after(0, self._popup.show)

    def _toggle_popup_from_hotkey(self) -> None:
        """Hotkey callback – schedule toggle on main thread."""
        if self._popup:
            self._popup.after(0, self._popup.toggle)

    # ------------------------------------------------------------------ #
    #  Paste                                                               #
    # ------------------------------------------------------------------ #

    def _paste_entry(self, entry: ClipEntry) -> None:
        """
        Restore clipboard content and simulate Ctrl+V.
        Runs on main thread (scheduled via popup.after).
        """
        # 1. Put content back on clipboard
        ok = set_clipboard_data(entry)
        if not ok:
            print(f"[Pinboard] Failed to restore clipboard for entry {entry.id}")
            return

        # 2. Update usage stats (in background to avoid blocking)
        if entry.id is not None:
            threading.Thread(
                target=self._db.update_used_count,
                args=(entry.id,),
                daemon=True,
            ).start()

        # 3. Simulate Ctrl+V (brief pause so the target window is focused)
        time.sleep(0.05)
        keyboard.send("ctrl+v")

    # ------------------------------------------------------------------ #
    #  Delete                                                              #
    # ------------------------------------------------------------------ #

    def _delete_entry(self, entry: ClipEntry) -> None:
        if entry.id is not None:
            self._db.delete(entry.id)

    # ------------------------------------------------------------------ #
    #  Tray menu actions                                                   #
    # ------------------------------------------------------------------ #

    def _toggle_pause(self, paused: bool) -> None:
        self._settings.set("pause_capture", paused)
        if self._listener:
            if paused:
                self._listener.pause()
            else:
                self._listener.resume()

    def _clear_history(self) -> None:
        self._db.clear_history()
        if self._popup:
            self._popup.after(0, self._popup.refresh)

    def _quit(self) -> None:
        print("[Pinboard] Exiting…")
        if self._listener:
            self._listener.stop()
        if self._hotkeys:
            self._hotkeys.unregister_all()
        if self._popup:
            self._popup.after(0, self._popup.destroy)
        if self._tray:
            self._tray.stop()

    # ------------------------------------------------------------------ #
    #  Settings                                                            #
    # ------------------------------------------------------------------ #

    def _open_settings(self) -> None:
        def on_save(updates: dict) -> None:
            old_hotkey = self._settings.get("hotkey")
            self._settings.update(updates)

            # Update startup registry
            #set_startup_registry(updates.get("startup_with_windows", False))

            # Re-bind hotkey if changed
            new_hotkey = updates.get("hotkey", old_hotkey)
            if new_hotkey and new_hotkey != old_hotkey:
                self._hotkeys.update_hotkey("open_popup", new_hotkey)

        if self._popup:
            SettingsDialog(self._popup, self._settings, on_save=on_save)


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    # Require Windows
    if sys.platform != "win32":
        print("Pinboard requires Windows 10 or 11.")
        sys.exit(1)

    # Request DPI awareness for crisp UI on HiDPI screens
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    app = Pinboard()
    app.run()


if __name__ == "__main__":
    main()
