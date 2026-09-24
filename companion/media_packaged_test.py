import threading

from media_bridge import WindowsMediaBridge


done = threading.Event()


def update(snapshot, artwork):
    print(
        snapshot.source,
        snapshot.title,
        snapshot.artist,
        snapshot.playing,
        len(artwork or b""),
    )
    if artwork:
        done.set()


bridge = WindowsMediaBridge(update, print)
bridge.start()
if not done.wait(8):
    raise SystemExit("packaged media test timed out")
bridge.stop()
print("PACKAGED_MEDIA_OK")
