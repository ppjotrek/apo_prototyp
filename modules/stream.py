from pathlib import Path

from flask import Response


PROJECT_DIR = Path(__file__).resolve().parent.parent
STREAM_VIDEO_PATH = PROJECT_DIR / "files" / "progress_spacecraft_docking_h264.mp4"


def stream_page() -> Response:
    html = """<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Symulowany stream</title>
  <style>
    html, body {
      width: 100%;
      height: 100%;
      margin: 0;
      background: #111;
    }
    video {
      display: block;
      width: 100%;
      height: 100%;
      object-fit: contain;
    }
  </style>
</head>
<body>
  <video autoplay muted loop playsinline controls>
    <source src="video" type="video/mp4">
  </video>
</body>
</html>
"""
    return Response(html, mimetype="text/html")
