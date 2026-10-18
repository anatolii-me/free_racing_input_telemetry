from __future__ import annotations

import ctypes
import math
import mmap
import os
import struct
import time

from .telemetry import Telemetry, clamp


# LMU 1.2 SharedMemoryInterface.hpp, 4-byte packed. Offsets verified
# against TinyPedal/pyLMUSharedMemory's mapping of the bundled SDK header.
MAP_NAME = "LMU_Data"
MAP_SIZE = 324820
TELEMETRY_OFFSET = 128464
VEHICLE_SIZE = 1888
MAX_VEHICLES = 104


def parse_lmu(data: bytes) -> tuple[float, Telemetry]:
    if len(data) < MAP_SIZE:
        raise ValueError("Short LMU map")
    active, player, has_vehicle = struct.unpack_from("<BBB", data, TELEMETRY_OFFSET)
    if not has_vehicle or not 1 <= active <= MAX_VEHICLES or player >= MAX_VEHICLES:
        raise ValueError("No LMU player car")
    at = TELEMETRY_OFFSET + 4 + player * VEHICLE_SIZE
    elapsed = struct.unpack_from("<d", data, at + 12)[0]
    velocity = struct.unpack_from("<3d", data, at + 184)
    gear = struct.unpack_from("<i", data, at + 352)[0]
    gas, brake, steer = struct.unpack_from("<3d", data, at + 388)
    if not all(math.isfinite(value) for value in (elapsed, *velocity, gas, brake, steer)):
        raise ValueError("Invalid LMU telemetry")
    if elapsed < 0 or not -1 <= gear <= 20:
        raise ValueError("Invalid LMU session")
    speed = math.sqrt(sum(component * component for component in velocity)) * 3.6
    return elapsed, Telemetry(
        gas=clamp(gas, 0, 1),
        brake=clamp(brake, 0, 1),
        steer=clamp(steer, -1, 1),
        speed_kmh=clamp(speed, 0, 999),
        gear=gear + 1,
        connected=True,
        label="LMU · LIVE",
        vehicle_available=True,
    )


class LmuReader:
    def __init__(self) -> None:
        self._map: mmap.mmap | None = None
        self._last_elapsed: float | None = None
        self._last_change = 0.0
        self._retry_at = 0.0

    def close(self) -> None:
        if self._map is not None:
            self._map.close()
            self._map = None

    def read(self) -> Telemetry:
        now = time.monotonic()
        if os.name != "nt":
            return Telemetry(label="ТОЛЬКО WINDOWS")
        if self._map is None and now >= self._retry_at:
            try:
                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel.OpenFileMappingW.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p)
                kernel.OpenFileMappingW.restype = ctypes.c_void_p
                kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
                handle = kernel.OpenFileMappingW(0x0004, 0, MAP_NAME)
                if not handle:
                    raise OSError("LMU map unavailable")
                kernel.CloseHandle(handle)
                self._map = mmap.mmap(-1, MAP_SIZE, tagname=MAP_NAME, access=mmap.ACCESS_READ)
            except (OSError, ValueError):
                self._retry_at = now + 1.0
        if self._map is None:
            return Telemetry(label="ОЖИДАНИЕ LMU")
        try:
            self._map.seek(0)
            elapsed, sample = parse_lmu(self._map.read(MAP_SIZE))
            if elapsed != self._last_elapsed:
                self._last_elapsed = elapsed
                self._last_change = now
            if now - self._last_change > 2.0:
                raise ValueError("Stale LMU telemetry")
            return sample
        except (OSError, ValueError, struct.error):
            self.close()
            self._retry_at = now + 1.0
            return Telemetry(label="ОЖИДАНИЕ LMU")
