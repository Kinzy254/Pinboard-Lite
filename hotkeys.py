"""
hotkeys.py - Global hotkey registration for Pinboard.

Uses the 'keyboard' library for hotkey binding. The popup toggle callback
is invoked from the hotkey thread, so UI code must schedule via after().
"""

import threading
from typing import Callable, Optional
import keyboard


class HotkeyManager:
    """Registers and manages global keyboard shortcuts."""

    def __init__(self):
        self._bindings: dict[str, str] = {}   # hotkey_str -> handler_id
        self._callbacks: dict[str, Callable] = {}
        self._lock = threading.Lock()

    def register(self, hotkey: str, callback: Callable, name: str = "") -> bool:
        """
        Register a global hotkey.
        Returns True on success.
        hotkey format: 'win+shift+v', 'ctrl+alt+p', etc.
        """
        with self._lock:
            # Unregister old binding for this name if exists
            if name and name in self._bindings:
                self.unregister(name)
            try:
                keyboard.add_hotkey(hotkey, callback, suppress=False)
                if name:
                    self._bindings[name] = hotkey
                    self._callbacks[name] = callback
                print(f"[HotkeyManager] Registered '{hotkey}' ({name})")
                return True
            except Exception as e:
                print(f"[HotkeyManager] Failed to register '{hotkey}': {e}")
                return False

    def unregister(self, name: str) -> None:
        with self._lock:
            if name in self._bindings:
                hotkey = self._bindings.pop(name)
                self._callbacks.pop(name, None)
                try:
                    keyboard.remove_hotkey(hotkey)
                except Exception as e:
                    print(f"[HotkeyManager] Error unregistering '{hotkey}': {e}")

    def unregister_all(self) -> None:
        names = list(self._bindings.keys())
        for name in names:
            self.unregister(name)

    def update_hotkey(self, name: str, new_hotkey: str) -> bool:
        """Change the hotkey for an existing binding."""
        with self._lock:
            callback = self._callbacks.get(name)
        if callback is None:
            print(f"[HotkeyManager] No binding named '{name}'")
            return False
        self.unregister(name)
        return self.register(new_hotkey, callback, name=name)
