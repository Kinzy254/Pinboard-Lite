from clipboard_listener import ClipboardListener
from models import ClipEntry

def on_clip(entry):
    for key, value in entry.to_dict().items():
        print(f"{key}: {value}")
    listener.stop()

listener = ClipboardListener(on_clip=on_clip)
listener.start()
input("...")

