"""
tray.py - System tray icon for Pinboard using pystray + Pillow.

The tray icon runs on its own thread. UI interactions are forwarded
via callbacks to the main application.
"""

import threading
from typing import Callable, Optional
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item


def _create_tray_icon_image(size: int = 64) -> Image.Image:
    """Draw a simple pin icon for the system tray."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle
    margin = 2
    draw.ellipse([margin, margin, size - margin, size - margin],
                 fill=(30, 120, 220, 255))

    # Simple pin shape
    cx = size // 2
    cy = size // 2
    r = size // 4

    # Circle head
    draw.ellipse([cx - r, cy - r - 4, cx + r, cy + r - 4], fill=(255, 255, 255, 240))
    # Pin body
    draw.polygon(
        [(cx, cy + r + 10), (cx - r // 2, cy - 2), (cx + r // 2, cy - 2)],
        fill=(255, 255, 255, 200),
    )
    return img


class TrayIcon:
    """Manages the system tray icon and its context menu."""

    def __init__(
        self,
        on_open: Callable,
        on_pause: Callable,
        on_clear_history: Callable,
        on_exit: Callable,
    ):
        self._on_open = on_open
        self._on_pause = on_pause
        self._on_clear_history = on_clear_history
        self._on_exit = on_exit
        self._icon: Optional[pystray.Icon] = None # type: ignore
        self._paused = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="TrayIcon")
        self._thread.start()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()

    def update_pause_state(self, paused: bool) -> None:
        self._paused = paused
        if self._icon:
            self._icon.update_menu()

    def _toggle_pause(self, icon, item_) -> None:
        self._paused = not self._paused
        self._on_pause(self._paused)
        icon.update_menu()

    def _run(self) -> None:
        image = _create_tray_icon_image()

        def pause_label(item_):
            return "▶ Resume Capture" if self._paused else "⏸ Pause Capture"

        menu = pystray.Menu(
            item("📌 Open Pinboard", lambda i, it: self._on_open(), default=True),
            item(pause_label, self._toggle_pause),
            pystray.Menu.SEPARATOR,
            item("🗑 Clear History", lambda i, it: self._on_clear_history()),
            pystray.Menu.SEPARATOR,
            item("✕ Exit", lambda i, it: self._on_exit()),
        )

        self._icon = pystray.Icon(
            name="Pinboard",
            icon=image,
            title="Pinboard – Clipboard Manager",
            menu=menu,
        )
        self._icon.run()
