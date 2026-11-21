import subprocess


SNAPSHOT_PATH = "/tmp/snapshot.jpg"


def capture_snapshot() -> str:
    cmd = [
        "rpicam-still",
        "-n",
        "--width", "1280",
        "--height", "720",
        "-t", "500",
        "-o", SNAPSHOT_PATH,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return SNAPSHOT_PATH
