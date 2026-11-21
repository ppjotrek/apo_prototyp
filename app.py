from flask import Flask, jsonify, send_file
import time
import subprocess


app = Flask(__name__)

@app.route("/")
def home():
	return "apo jest zajebiste"

@app.route("/api/sensors")
def get_sensors():
	data = {
		"timestamp" : int(time.time()),
		"status" : "ok"
	}
	return jsonify(data)

@app.route("/api/snapshot")
def get_snapshot():
	output_path = "/tmp/snapshot.jpg"
	cmd = [
		"rpicam-still",
		"-n",
		"--width", "1280",
		"--height", "720",
		"-t", "500",
		"-o", output_path,
	]
	result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
	if result.returncode != 0:
		return jsonify({"error" : "Camera failed", "details" : result.stderr.strip()}), 500
	return send_file(output_path, mimetype="image/jpeg")

if __name__ == "__main__":
	app.run(host="0.0.0.0", port=5000)
