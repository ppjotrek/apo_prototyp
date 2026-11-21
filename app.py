from flask import Flask, jsonify, send_file, request
import time
from smbus2 import SMBus
import lgpio
import spidev


app = Flask(__name__)

I2C_BUS = 1
MAG_ADDR = 0x0D

SPI_BUS = 0
SPI_DEV = 0        # /dev/spidev0.0 (CSN -> GPIO 8)
CE_PIN = 22        # BCM 22
RF_CHANNEL = 76    # Kanał 2.4 GHz (0..125) - zgodny z nadajnikiem
RF_ADDR = b"NODE1"   # 5-bajtowy adres rury RX - zgodny z nadajnikiem
PAYLOAD_SIZE = 32  # Rozmiar pakietu w bajtach (1..32)

rf_lock = threading.Lock()
latest_rf = {
    "received": False,
    "timestamp": None,
    "channel": RF_CHANNEL,
    "address": RF_ADDR.decode("latin1"),
    "hex": None,
    "text": None,
    "bytes": [],
    "error": None,
}

class NRF24Receiver:
    R_CONFIG = 0x00
    R_EN_AA = 0x01
    R_EN_RXADDR = 0x02
    R_SETUP_AW = 0x03
    R_RF_CH = 0x05
    R_RF_SETUP = 0x06
    R_STATUS = 0x07
    R_RX_ADDR_P0 = 0x0A
    R_RX_PW_P0 = 0x11

    CMD_R_REGISTER = 0x00
    CMD_W_REGISTER = 0x20
    CMD_R_RX_PAYLOAD = 0x61
    CMD_FLUSH_RX = 0xE2

    def __init__(self, bus: int, dev: int, ce_pin: int, channel: int, addr: bytes, payload_len: int):
        self.ce_pin = ce_pin
        self.channel = channel
        self.addr = addr[:5]
        self.payload_len = payload_len

        self.spi = spidev.SpiDev()
        self.spi.open(bus, dev)
        self.spi.max_speed_hz = 1_000_000
        self.spi.mode = 0

        self.chip = lgpio.gpiochip_open(0)
        lgpio.gpio_claim_output(self.chip, self.ce_pin, 0)

    def ce(self, active: bool) -> None:
        lgpio.gpio_write(self.chip, self.ce_pin, 1 if active else 0)

    def write_reg(self, reg: int, data) -> None:
        values = [data] if isinstance(data, int) else list(data)
        self.spi.xfer2([self.CMD_W_REGISTER | (reg & 0x1F)] + values)

    def read_reg(self, reg: int, length: int = 1):
        resp = self.spi.xfer2([self.CMD_R_REGISTER | (reg & 0x1F)] + [0x00] * length)
        return resp[1] if length == 1 else resp[1:]

    def setup_rx(self) -> None:
        self.ce(False)
        time.sleep(0.01)
        self.write_reg(self.R_EN_AA, 0x01)
        self.write_reg(self.R_EN_RXADDR, 0x01)
        self.write_reg(self.R_SETUP_AW, 0x03)        # Adres 5-bajtowy
        self.write_reg(self.R_RF_CH, self.channel)
        self.write_reg(self.R_RF_SETUP, 0x06)        # 1 Mbps, 0 dBm
        self.write_reg(self.R_RX_ADDR_P0, list(self.addr))
        self.write_reg(self.R_RX_PW_P0, self.payload_len)
        self.write_reg(self.R_STATUS, 0x70)          # Kasowanie flag IRQ
        self.spi.xfer2([self.CMD_FLUSH_RX])
        self.write_reg(self.R_CONFIG, 0x0B)          # PWR_UP + PRIM_RX + CRC 1B
        time.sleep(0.005)
        self.ce(True)

    def poll_once(self):
        status = self.read_reg(self.R_STATUS)
        if status & 0x40:  # RX_DR - nowy pakiet w buforze
            raw = self.spi.xfer2([self.CMD_R_RX_PAYLOAD] + [0x00] * self.payload_len)[1:]
            self.write_reg(self.R_STATUS, 0x40)
            return bytes(raw)
        return None

    def close(self) -> None:
        try:
            self.ce(False)
            lgpio.gpiochip_close(self.chip)
        finally:
            self.spi.close()


def rf_listener_loop() -> None:
    rx = NRF24Receiver(SPI_BUS, SPI_DEV, CE_PIN, RF_CHANNEL, RF_ADDR, PAYLOAD_SIZE)
    try:
        rx.setup_rx()
        while True:
            packet = rx.poll_once()
            if packet is not None:
                clean = packet.rstrip(b"\x00")
                with rf_lock:
                    latest_rf.update({
                        "received": True,
                        "timestamp": int(time.time()),
                        "channel": RF_CHANNEL,
                        "address": RF_ADDR.decode("latin1"),
                        "hex": packet.hex(),
                        "text": clean.decode("utf-8", errors="replace"),
                        "bytes": list(packet),
                        "error": None,
                    })
            time.sleep(0.02)
    except Exception as exc:
        with rf_lock:
            latest_rf["error"] = str(exc)
    finally:
        rx.close()


def read_rf() -> dict:
    with rf_lock:
        return dict(latest_rf)

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

@app.route("/api/rf")
def api_rf():
    return jsonify(read_rf())

@app.route("/api/magnetometer")
def api_mag():
	try:
		data = read_mag()
		return jsonify(data)
	except Exception as exc:
		return jsonify({"error" : "Failed to read", "details" : str(exc)}), 500

@app.route("/api/sensors")
def api_sensors():
    # Opcjonalnie: /api/sensors?only=magnetometer lub /api/sensors?only=rf
    only = request.args.get("only")
    payload = {"timestamp": int(time.time())}

    if only in (None, "magnetometer"):
        try:
            payload["magnetometer"] = read_magnetometer()
        except Exception as exc:
            payload["magnetometer"] = {"ok": False, "error": str(exc)}

    if only in (None, "rf"):
        payload["rf"] = read_rf()

    return jsonify(payload)

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
	threading.Thread(target=rf_listener_loop, daemon=True).start()
	app.run(host="0.0.0.0", port=5000)
