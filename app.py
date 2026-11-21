from flask import Flask, jsonify, send_file
import time
from smbus2 import SMBus


app = Flask(__name__)

I2C_BUS = 1
MAG_ADDR = 0x0D

def _int16(lsb: int, msb: int) -> int:
	value = (msb << 8) | lsb
	return value - 65536 if value >=32768 else value

def init_mag(bus: SMBus) -> None:
	bus.write_byte_data(MAG_ADDR, 0x0B, 0x01) #reset
	bus.write_byte_data(MAG_ADDR, 0x09, 0x1D) #tryb ciągły
	time.sleep(0.02)

def read_mag() -> dict:
	with SMBus(I2C_BUS) as bus:
		init_mag(bus)
		raw = bus.read_i2c_block_data(MAG_ADDR, 0x00, 6)
	
	return {
		"addr" : "0x0d",
		"chip" : "QMC5883L",
		"x" : _int16(raw[0], raw[1]),
		"y" : _int16(raw[2], raw[3]),
		"z" : _int16(raw[4], raw[5])
		}

@app.route("/")
def home():
	return "apo jest zajebiste"

@app.route("/api/magnetometer")
def api_mag():
	try:
		data = read_mag()
		return jsonify(data)
	except Exception as exc:
		return jsonify({"error" : "Failed to read", "details" : str(exc)}), 500

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
