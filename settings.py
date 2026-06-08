"""
settings.py - Application settings management (JSON-backed config).
"""

import json
import os
from pathlib import Path
from typing import Any


# Default config values
DEFAULT_SETTINGS: dict[str, Any] = {
    "max_history": 500,
    "startup_with_windows": False,
    "hotkey": "win+shift+v",
    "theme": "dark",
    "popup_width": 420,
    "show_thumbnails": True,
    "pause_capture": False,
    "edge_icon_y": 120,
}

# Config file lives next to the script
CONFIG_DIR = Path(os.environ.get("APPDATA", ".")) / "Pinboard"
CONFIG_PATH = CONFIG_DIR / "settings.json"


class Settings:
    """Loads/saves user settings from a JSON file."""

    def __init__(self):
        self._data: dict[str, Any] = dict(DEFAULT_SETTINGS)
        self._load()

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default if default is not None else DEFAULT_SETTINGS.get(key))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def update(self, updates: dict) -> None:
        self._data.update(updates)
        self._save()

    def all(self) -> dict:
        return dict(self._data)

    # ------------------------------------------------------------------ #
    #  Internals                                                           #
    # ------------------------------------------------------------------ #

    def _load(self) -> None:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                # Merge saved values over defaults (so new keys get defaults)
                self._data.update(saved)
        except Exception as e:
            print(f"[Settings] Failed to load config: {e}")

    def _save(self) -> None:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            print(f"[Settings] Failed to save config: {e}")


# Singleton instance for global access to settings (ensures only one instance manages the config file) 
_instance: Settings | None = None


def get_settings() -> Settings:
    global _instance
    if _instance is None:
        _instance = Settings()
    return _instance
