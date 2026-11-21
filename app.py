import time
import threading

from flask import Flask, jsonify, request, send_file

from modules.camera import capture_snapshot
from modules.magnetometer import read_mag
from modules.rf import rf_listener_loop, read_rf
from modules.stream import STREAM_VIDEO_PATH, stream_page

app = Flask(__name__)

@app.route("/")
def home():
    return "apo jest zajebiste"

@app.route("/api/rf")
def api_rf():
    return jsonify(read_rf())

@app.route("/api/magnetometer")
def api_mag():
    try:
        data = read_mag()
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": "Failed to read", "details": str(exc)}), 500

@app.route("/api/sensors")
def api_sensors():
    only = request.args.get("only")
    payload = {"timestamp": int(time.time())}

    if only in (None, "magnetometer"):
        try:
            payload["magnetometer"] = read_mag()
        except Exception as exc:
            payload["magnetometer"] = {"ok": False, "error": str(exc)}

    if only in (None, "rf"):
        payload["rf"] = read_rf()

    return jsonify(payload)

@app.route("/api/snapshot")
def get_snapshot():
    try:
        output_path = capture_snapshot()
        return send_file(output_path, mimetype="image/jpeg")
    except RuntimeError as exc:
        return jsonify({"error": "Camera failed", "details": str(exc)}), 500

@app.route("/stream/")
def video_stream():
    return stream_page()

@app.route("/stream/video")
def video_stream_file():
    if not STREAM_VIDEO_PATH.is_file():
        return jsonify({"error": "Stream video not found", "details": str(STREAM_VIDEO_PATH)}), 404
    return send_file(
        STREAM_VIDEO_PATH,
        mimetype="video/mp4",
        conditional=True,
        as_attachment=False,
    )

if __name__ == "__main__":
    threading.Thread(target=rf_listener_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
