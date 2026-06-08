"""
clipboard_listener.py - Native Windows clipboard listener using WM_CLIPBOARDUPDATE.

Uses AddClipboardFormatListener instead of polling. A hidden Win32 window receives
clipboard change notifications, reads the clipboard data, and fires a callback.
"""

import threading
import ctypes
import ctypes.wintypes
import struct
import io
from typing import Callable, Optional

import win32api
import win32clipboard
import win32con
import win32gui

from models import ClipEntry
from utils import dib_to_png, create_hdrop
from datetime import datetime


# Windows message constant
WM_CLIPBOARDUPDATE = 0x031D

# HTML clipboard format name
HTML_FORMAT_NAME = "HTML Format"


class ClipboardListener:
    """
    Runs a hidden Win32 window on a background thread to receive
    WM_CLIPBOARDUPDATE messages without polling.
    """

    def __init__(self, on_clip: Callable[[ClipEntry], None]):
        self._on_clip = on_clip
        self._hwnd: Optional[int] = None
        self._thread = threading.Thread(target=self._run_message_loop, daemon=True, name="ClipboardListener")
        self._paused = False
        self._started = threading.Event()

    # ------------------------------------------------------------------ #
    #  Public                                                              #
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        self._thread.start()
        self._started.wait(timeout=3)

    def stop(self) -> None:
        if self._hwnd:
            try:
                win32api.PostMessage(self._hwnd, win32con.WM_DESTROY, 0, 0)
            except Exception:
                pass

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    @property
    def is_paused(self) -> bool:
        return self._paused

    # ------------------------------------------------------------------ #
    #  Win32 message loop                                                  #
    # ------------------------------------------------------------------ #

    def _run_message_loop(self) -> None: 
        """Create a hidden window and pump messages."""
        hinst = win32api.GetModuleHandle(None)

        wndclass = win32gui.WNDCLASS()
        wndclass.hInstance = hinst
        wndclass.lpszClassName = "PinboardClipListener"
        wndclass.lpfnWndProc = self._wnd_proc

        try:
            win32gui.RegisterClass(wndclass)
        except Exception:
            pass  # Already registered (e.g. restarted)

        self._hwnd = win32gui.CreateWindow(
            wndclass.lpszClassName,
            "Pinboard Clipboard Listener",
            0, 0, 0, 0, 0,
            win32con.HWND_MESSAGE,   # Message-only window
            0, hinst, None,
        )

        # Register for clipboard change notifications
        ctypes.windll.user32.AddClipboardFormatListener(self._hwnd)

        self._started.set()

        # Standard Win32 message pump
        win32gui.PumpMessages()

        # Clean up
        ctypes.windll.user32.RemoveClipboardFormatListener(self._hwnd)

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_CLIPBOARDUPDATE:
            print("[ClipboardListener]: New clipboard item")
            if not self._paused:
                self._handle_clipboard_update()
            return 0
        if msg == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    # ------------------------------------------------------------------ #
    #  Clipboard reading                                                   #
    # ------------------------------------------------------------------ #

    def _handle_clipboard_update(self) -> None:
        """Read clipboard content and dispatch to callback."""
        entry = self._read_clipboard()
        if entry is not None:
            try:
                self._on_clip(entry)
            except Exception as e:
                print(f"[ClipboardListener] Callback error: {e}")

    def _read_clipboard(self) -> Optional[ClipEntry]:
        """
        Attempt to open the clipboard and read the highest-priority format.
        Returns a ClipEntry or None if nothing useful was found.
        """
        for attempt in range(5):
            try:
                win32clipboard.OpenClipboard(None)
                break
            except Exception:
                import time
                time.sleep(0.05 * (attempt + 1))
        else:
            print("[ClipboardListener] Could not open clipboard after retries")
            return None

        try:
            entry = self._extract_entry()
            return entry
        except Exception as e:
            print(f"[ClipboardListener] Read error: {e}")
            return None
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass

    def _extract_entry(self) -> Optional[ClipEntry]:
        """Extract clipboard data into a ClipEntry. Clipboard must be open."""
        now = datetime.now().isoformat()

        

        # --- Image (CF_DIB) ---
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB):
            try:
                dib_data = win32clipboard.GetClipboardData(win32con.CF_DIB)
                png_path = dib_to_png(dib_data)
                if png_path:
                    return ClipEntry(
                        type="image",
                        content="[Image]",
                        image_path=png_path,
                        created_at=now,
                    )
            except Exception as e:
                print(f"[ClipboardListener] DIB error: {e}")

        # --- File drop (CF_HDROP) ---
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP):
            try:
                files = win32clipboard.GetClipboardData(win32con.CF_HDROP)
                if files:
                    content = "\n".join(files)
                    return ClipEntry(
                        type="files",
                        content=content,
                        created_at=now,
                    )
            except Exception as e:
                print(f"[ClipboardListener] HDROP error: {e}")

        # --- HTML Format ---
        html_fmt = win32clipboard.RegisterClipboardFormat(HTML_FORMAT_NAME)
        html_content = None
        if win32clipboard.IsClipboardFormatAvailable(html_fmt):
            try:
                raw = win32clipboard.GetClipboardData(html_fmt)
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                html_content = raw
            except Exception as e:
                print(f"[ClipboardListener] HTML format error: {e}")

        # --- Unicode text (CF_UNICODETEXT) ---
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            try:
                text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                if text and text.strip():
                    entry_type = "html" if html_content else "text"
                    return ClipEntry(
                        type=entry_type,
                        content=text,
                        html_content=html_content,
                        created_at=now,
                    )
            except Exception as e:
                print(f"[ClipboardListener] Unicode text error: {e}")

        return None  # Nothing useful found

# ------------------------------------------------------------------ #
#  Clipboard restore helpers (used by paste logic)                    #
# ------------------------------------------------------------------ #

def set_clipboard_data(entry: ClipEntry) -> bool:
    """
    Put the given ClipEntry onto the Windows clipboard
    in the appropriate format(s) so Ctrl+V works correctly.
    """
    for attempt in range(5):
        try:
            win32clipboard.OpenClipboard(None)
            break
        except Exception as e:
            print(f"[Set Clipboard] Error on attempt {attempt}: {e}")
            import time
            time.sleep(0.05 * (attempt + 1))
    else:
        return False

    try:
        win32clipboard.EmptyClipboard()

        if entry.type == "text":
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, entry.content)

        elif entry.type == "html":
            # Restore both plain text and HTML format
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, entry.content)
            if entry.html_content:
                html_fmt = win32clipboard.RegisterClipboardFormat(HTML_FORMAT_NAME)
                encoded = entry.html_content.encode("utf-8")
                win32clipboard.SetClipboardData(html_fmt, encoded)

        elif entry.type == "files":
            # Restore as CF_HDROP
            paths = entry.content.split("\n")
            win32clipboard.SetClipboardData(win32con.CF_HDROP, create_hdrop(paths))

        elif entry.type == "image":
            # Restore image from saved PNG thumbnail
            win32clipboard.SetClipboardData(win32con.CF_DIB, entry.image_dib)

        return True
    except Exception as e:
        print(f"[restore_to_clipboard] Error: {e}")
        return False
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass

