import time

from smbus2 import SMBus


I2C_BUS = 1
MAG_ADDR = 0x0D


def _int16(lsb: int, msb: int) -> int:
    value = (msb << 8) | lsb
    return value - 65536 if value >= 32768 else value


def init_mag(bus: SMBus) -> None:
    bus.write_byte_data(MAG_ADDR, 0x0B, 0x01)
    bus.write_byte_data(MAG_ADDR, 0x09, 0x1D)
    time.sleep(0.02)


def read_mag() -> dict:
    with SMBus(I2C_BUS) as bus:
        init_mag(bus)
        raw = bus.read_i2c_block_data(MAG_ADDR, 0x00, 6)

    return {
        "addr": "0x0d",
        "chip": "QMC5883L",
        "x": _int16(raw[0], raw[1]),
        "y": _int16(raw[2], raw[3]),
        "z": _int16(raw[4], raw[5]),
    }
