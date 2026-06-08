# 📌 Pinboard

📋 **A lightweight, high-performance, and native clipboard manager built for Windows.**

Pinboard runs quietly in your system tray, listening for clipboard changes using native Win32 events (no performance-heavy polling). When called upon via a global hotkey, it pops up a sleek, always-on-top, dark-themed menu right at your cursor to let you quickly search, cycle, paste, or pin your clipboard history.

[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%2F%2011-blue?style=for-the-badge&logo=windows)](https://www.microsoft.com/windows)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=for-the-badge&logo=python)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge&logo=opensourceinitiative)](LICENSE)
[![Release](https://img.shields.io/badge/release-v1.0.0--stable-orange?style=for-the-badge)]()

---

## ✨ Features

* **🚀 Native Performance:** Uses Windows `AddClipboardFormatListener` to receive immediate OS level `WM_CLIPBOARDUPDATE` event notifications. Completely avoids expensive CPU-polling cycles.
* **📦 Rich Data Types:** Captures, stores, and restores multiple data types seamlessly:
  * 📝 Plain Text
  * 🌐 HTML Formatting
  * 📁 Files & Folders (`CF_HDROP` structures)
  * 🖼️ Images (Converts raw Windows `DIB` data to lightweight compressed PNG files for local storage/UI thumbnails)
* **🗃️ Thread-Safe Storage:** Uses an embedded SQLite database configured in Write-Ahead Logging (**WAL**) mode coupled with multi-threaded Python locks to guarantee crisp data persistence without blocking the main UI thread.
* **🎹 Keyboard First:** Trigger the popup anytime with a global shortcut (`Win + Shift + V` by default), navigate seamlessly with your keyboard arrow keys, and instantly auto-paste selections.
* **📌 Pins & Favorites:** Pin frequently used code snippets, text blocks, or files to keep them anchored to the top of your layout list.
* **🎨 Modern UI:** Sleek, high-DPI aware, dark-themed CustomTkinter popup window designed to position itself intelligently next to your cursor, fading out naturally when focus is lost or after a paste execution.

---

## 🛠️ Tech Stack & Architecture

Pinboard relies on a decoupled, event-driven module architecture:

* **UI Layer (`ui_popup.py`):** Powered by `customtkinter` for crisp typography and an elegant dark appearance.
* **Listener Layer (`clipboard_listener.py`):** Spawns a background thread creating a hidden Win32 Window message loop to tap directly into Windows OS events.
* **Persistence Layer (`database.py` & `models.py`):** Lightweight SQLite infrastructure with optimized PRAGMAs (`synchronous=NORMAL`) and structured dataclass modeling.
* **System Integration (`tray.py` & `hotkeys.py`):** System tray status controls managed by `pystray`, and OS-wide hotkey interception via the `keyboard` library.

---

## 🚀 Getting Started

### Prerequisites
* Windows 10 or Windows 11
* Python 3.10 or higher (If running from source)

### Installation (Pre-compiled Binary)
1. Head over to the [Releases]() section.
2. Download the latest `Pinboard.exe`.
3. Move it to your preferred folder and run it. It will instantly instantiate a tray icon and start listening!

### Running from Source
If you wish to modify the code or run it locally via python, follow these steps:

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/yourusername/pinboard.git](https://github.com/yourusername/pinboard.git)
   cd pinboard