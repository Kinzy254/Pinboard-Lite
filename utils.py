import io
from pathlib import Path
import struct
from tempfile import NamedTemporaryFile
import time
from typing import Optional

from PIL import Image


def create_hdrop(paths: list[str]) -> None:
    """Build and set a CF_HDROP structure for a list of file paths."""
    # DROPFILES structure: size(4) + pt(8) + fNC(4) + fWide(4) + paths(var)
    # Each path is null-terminated UTF-16LE, list terminated by double-null.
    paths_encoded = b""
    for p in paths:
        paths_encoded += (p + "\0").encode("utf-16-le")
    paths_encoded += b"\x00\x00"  # double-null terminator

    dropfiles_size = 20  # sizeof(DROPFILES)
    header = struct.pack(
        "<IIIII",
        dropfiles_size,  # pFiles offset
        0, 0,            # pt (x, y)
        0,               # fNC
        1,               # fWide (Unicode)
    )
    drop_data = header + paths_encoded

    #mem = ctypes.windll.kernel32.GlobalAlloc(0x0042, len(drop_data))  # GMEM_MOVEABLE|GMEM_ZEROINIT
    #ptr = ctypes.windll.kernel32.GlobalLock(mem)
    #ctypes.memmove(ptr, drop_data, len(drop_data))
    #ctypes.windll.kernel32.GlobalUnlock(mem)
    #win32clipboard.SetClipboardData(win32con.CF_HDROP, mem)

    return drop_data

def dib_to_png(dib_data: bytes) -> Path:
    """Convert DIB (Device Independent Bitmap) data to PNG format."""
        
    output_path = NamedTemporaryFile(delete=False, suffix=".png").name

    
    try:

        # CF_DIB is a BITMAPINFOHEADER + pixel data (no file header).
        # We reconstruct a BMP by prepending a BITMAPFILEHEADER.
        bih_size = struct.unpack_from("<I", dib_data, 0)[0]
        width    = struct.unpack_from("<i", dib_data, 4)[0]
        height   = struct.unpack_from("<i", dib_data, 8)[0]
        bit_count = struct.unpack_from("<H", dib_data, 14)[0]

        # Size of colour table
        color_used = struct.unpack_from("<I", dib_data, 32)[0]
        if color_used == 0 and bit_count <= 8:
            color_used = 1 << bit_count
        color_table_size = color_used * 4

        pixel_data_offset = 14 + bih_size + color_table_size
        file_size = 14 + len(dib_data)

        bmp_file_header = struct.pack(
            "<2sIHHI",
            b"BM",
            file_size,
            0, 0,
            pixel_data_offset,
        )
        bmp_data = bmp_file_header + dib_data

        img = Image.open(io.BytesIO(bmp_data))
        
        img.save(output_path, format="PNG")

        return output_path
    
    except Exception as e:
        print(f"[DIB→PNG] error: {e}")
        return None
    
def image_to_dib(path: str) -> bytes | None:
    """Read a PNG file and returns CF_DIB bytes."""
    try:
        from PIL import Image
        import io as _io

        img = Image.open(path).convert("RGB")
        buf = _io.BytesIO()
        img.save(buf, format="BMP")
        bmp_data = buf.getvalue()

        # Strip the 14-byte BMP file header to get raw DIB
        dib_data = bmp_data[14:]
        
        return dib_data
    except Exception as e:
        print(f"[Image→DIB] Error: {e}")
    
def format_time_ago(iso_str: str) -> str:
    """Return human-readable relative time string."""
    if not iso_str:
        return ""
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(iso_str)
        delta = datetime.now() - dt
        s = int(delta.total_seconds())
        if s < 60:
            return "just now"
        if s < 3600:
            return f"{s // 60}m ago"
        if s < 86400:
            return f"{s // 3600}h ago"
        return f"{s // 86400}d ago"
    except Exception:
        return ""

def truncate(text: str, max_len: int = 80) -> str:
    text = text.strip().replace("\n", " ").replace("\r", "")
    return text[:max_len] + "…" if len(text) > max_len else text

