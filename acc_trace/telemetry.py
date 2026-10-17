from __future__ import annotations

import math
import mmap
import os
import struct
import time
import ctypes
from dataclasses import dataclass


# The first eight fields of ACC's 4-byte packed SPageFilePhysics.
# See ACCSharedMemoryDocumentationV1.8.12, SPageFilePhysics.
PHYSICS_HEAD = struct.Struct("<ifffiiff")


@dataclass(frozen=True)
class Telemetry:
    gas: float = 0.0
    brake: float = 0.0
    steer: float = 0.0
    speed_kmh: float = 0.0
    gear: int = 1  # ACC: 0=R, 1=N, 2=1, ...
    connected: bool = False
    label: str = "ОЖИДАНИЕ ACC"
    vehicle_available: bool = False


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def parse_physics(data: bytes) -> tuple[int, Telemetry]:
    packet, gas, brake, _fuel, gear, _rpm, steer, speed = PHYSICS_HEAD.unpack_from(data)
    if not all(math.isfinite(value) for value in (gas, brake, steer, speed)):
        raise ValueError("Non-finite ACC physics values")
    return packet, Telemetry(
        gas=clamp(gas, 0, 1),
        brake=clamp(brake, 0, 1),
        steer=clamp(steer, -1, 1),
        speed_kmh=clamp(speed, 0, 999),
        gear=gear,
        connected=True,
        label="ACC · LIVE",
        vehicle_available=True,
    )


class AccReader:
    def __init__(self) -> None:
        self._map: mmap.mmap | None = None
        self._last_packet: int | None = None
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
                # mmap(tagname=...) creates a new empty mapping when none exists.
                # OpenFileMappingW first so an idle overlay never shadows the game.
                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel32.OpenFileMappingW.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p)
                kernel32.OpenFileMappingW.restype = ctypes.c_void_p
                kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
                handle = kernel32.OpenFileMappingW(0x0004, 0, r"Local\acpmf_physics")
                if not handle:
                    raise OSError("ACC mapping is unavailable")
                kernel32.CloseHandle(handle)
                self._map = mmap.mmap(-1, PHYSICS_HEAD.size, tagname=r"Local\acpmf_physics", access=mmap.ACCESS_READ)
            except (OSError, ValueError):
                self._retry_at = now + 1.0
        if self._map is None:
            return Telemetry()
        try:
            self._map.seek(0)
            packet, sample = parse_physics(self._map.read(PHYSICS_HEAD.size))
            if packet != self._last_packet:
                self._last_packet = packet
                self._last_change = now
            if packet <= 0 or now - self._last_change > 2.0:
                self.close()
                self._retry_at = now + 1.0
                return Telemetry()
            return sample
        except (OSError, ValueError, struct.error):
            self.close()
            self._retry_at = now + 1.0
            return Telemetry()


class DemoReader:
    def __init__(self) -> None:
        self._start = time.monotonic()

    def read(self) -> Telemetry:
        t = time.monotonic()
        phase = (t - self._start) % 4.6
        gas = clamp((phase - .9) / .45, 0, 1) * clamp((3.05 - phase) / .5, 0, 1)
        brake = max(clamp((.95 - phase) / .4, 0, 1), clamp((phase - 2.85) / .35, 0, 1))
        return Telemetry(gas, brake, math.sin(t * 0.85) * 0.68, 128 + 18 * math.sin(t * 0.48), 4, True, "ДЕМО · PREVIEW", True)
