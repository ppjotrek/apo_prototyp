import time

try:
    from smbus2 import SMBus
    HAS_SMBUS = True
except (ImportError, ModuleNotFoundError):
    HAS_SMBUS = False
    SMBus = None
    print("Brak smbus2 (Windows) - magnetometr działa w trybie symulacji.")

I2C_BUS = 1
MAG_ADDR = 0x0D

def _int16(lsb: int, msb: int) -> int:
    value = (msb << 8) | lsb
    return value - 65536 if value >= 32768 else value

def init_mag(bus) -> None:
    if not HAS_SMBUS or bus is None:
        return
    bus.write_byte_data(MAG_ADDR, 0x0B, 0x01)
    bus.write_byte_data(MAG_ADDR, 0x09, 0x1D)
    time.sleep(0.02)

def read_mag() -> dict:
    if not HAS_SMBUS:
        return {"x": 0.0, "y": 0.0, "z": 0.0}  # Domyślne wartości testowe dla Windowsa

    try:
        with SMBus(I2C_BUS) as bus:
            init_mag(bus)
            data = bus.read_i2c_block_data(MAG_ADDR, 0x00, 6)
            x = _int16(data[0], data[1])
            y = _int16(data[2], data[3])
            z = _int16(data[4], data[5])
            return {"x": x, "y": y, "z": z}
    except Exception as e:
        print(f"Błąd odczytu magnetometru: {e}")
        return {"x": 0.0, "y": 0.0, "z": 0.0}