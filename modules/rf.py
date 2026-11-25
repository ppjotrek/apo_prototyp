import threading
import time

try:
    import lgpio
    HAS_LGPIO = True
except (ImportError, ModuleNotFoundError):
    HAS_LGPIO = False
    lgpio = None
    print("Brak lgpio (Windows) - moduł RF działa w trybie symulacji.")
try:
    import spidev
    HAS_SPIDEV = True
except (ImportError, ModuleNotFoundError):
    HAS_SPIDEV = False
    spidev = None
    print("Brak spidev (Windows) - komunikacja SPI w module RF działa w trybie symulacji.")


SPI_BUS = 0
SPI_DEV = 0
CE_PIN = 22
RF_CHANNEL = 76
RF_ADDR = b"NODE1"
PAYLOAD_SIZE = 32

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
        self.write_reg(self.R_SETUP_AW, 0x03)
        self.write_reg(self.R_RF_CH, self.channel)
        self.write_reg(self.R_RF_SETUP, 0x06)
        self.write_reg(self.R_RX_ADDR_P0, list(self.addr))
        self.write_reg(self.R_RX_PW_P0, self.payload_len)
        self.write_reg(self.R_STATUS, 0x70)
        self.spi.xfer2([self.CMD_FLUSH_RX])
        self.write_reg(self.R_CONFIG, 0x0B)
        time.sleep(0.005)
        self.ce(True)

    def poll_once(self):
        status = self.read_reg(self.R_STATUS)
        if status & 0x40:
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
    rx = None
    try:
        rx = NRF24Receiver(SPI_BUS, SPI_DEV, CE_PIN, RF_CHANNEL, RF_ADDR, PAYLOAD_SIZE)
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
        if rx is not None:
            rx.close()


def read_rf() -> dict:
    with rf_lock:
        return dict(latest_rf)
