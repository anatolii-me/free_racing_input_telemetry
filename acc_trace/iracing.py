from __future__ import annotations

import ctypes
import math
import mmap
import os
import struct
import time

from .telemetry import Telemetry, clamp


MAP_NAME = r"Local\IRSDKMemMapFileName"
MAP_SIZE = 1164 * 1024  # iRacing SDK's live map allocation
REQUIRED = ("Throttle", "Brake", "SteeringWheelAngle", "Speed", "Gear")


def parse_iracing(data: bytes) -> tuple[int, Telemetry]:
    """Read one complete iRacing SDK telemetry row from a map snapshot."""
    if len(data) < 112:
        raise ValueError("Short iRacing header")
    version, status, _rate, _update, _len, _session, count, headers_at, buffers, row_len = struct.unpack_from("<10i", data)
    if version < 1 or not status & 1 or not 1 <= buffers <= 4 or not 1 <= count <= 4096:
        raise ValueError("Invalid iRacing header")
    if row_len <= 0 or row_len > 65536 or headers_at < 112 or headers_at + count * 144 > len(data):
        raise ValueError("Invalid iRacing variables")
    rows = []
    for index in range(buffers):
        tick, offset, tick_begin = struct.unpack_from("<3i", data, 48 + 16 * index)
        if tick > 0 and tick_begin <= tick and offset >= 0 and offset + row_len <= len(data):
            rows.append((tick, offset))
    if not rows:
        raise ValueError("No complete iRacing row")
    tick, row_at = max(rows)
    wanted = set(REQUIRED) | {"SteeringWheelAngleMax"}
    values: dict[str, float] = {}
    for index in range(count):
        at = headers_at + index * 144
        kind, offset, elements = struct.unpack_from("<3i", data, at)
        name = data[at + 16:at + 48].split(b"\0", 1)[0].decode("ascii", "ignore")
        if name not in wanted or elements < 1 or kind not in (2, 4, 5):
            continue
        fmt = {2: "<i", 4: "<f", 5: "<d"}[kind]
        if 0 <= offset <= row_len - struct.calcsize(fmt):
            values[name] = float(struct.unpack_from(fmt, data, row_at + offset)[0])
    if not set(REQUIRED) <= values.keys() or not all(math.isfinite(v) for v in values.values()):
        raise ValueError("Missing or invalid iRacing telemetry")
    maximum = values.get("SteeringWheelAngleMax", math.radians(270))
    if maximum <= 0:
        maximum = math.radians(270)
    return tick, Telemetry(
        gas=clamp(values["Throttle"], 0, 1),
        brake=clamp(values["Brake"], 0, 1),
        steer=clamp(values["SteeringWheelAngle"] / maximum, -1, 1),
        speed_kmh=clamp(values["Speed"] * 3.6, 0, 999),
        gear=int(values["Gear"]) + 1,
        connected=True,
        label="iRacing · LIVE",
        vehicle_available=True,
    )


class IracingReader:
    def __init__(self) -> None:
        self._map: mmap.mmap | None = None
        self._last_tick: int | None = None
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
                    raise OSError("iRacing map unavailable")
                kernel.CloseHandle(handle)
                self._map = mmap.mmap(-1, MAP_SIZE, tagname=MAP_NAME, access=mmap.ACCESS_READ)
            except (OSError, ValueError):
                self._retry_at = now + 1.0
        if self._map is None:
            return Telemetry(label="ОЖИДАНИЕ iRACING")
        try:
            self._map.seek(0)
            tick, sample = parse_iracing(self._map.read(MAP_SIZE))
            if tick != self._last_tick:
                self._last_tick = tick
                self._last_change = now
            if now - self._last_change > 2.0:
                raise ValueError("Stale iRacing data")
            return sample
        except (OSError, ValueError, struct.error):
            self.close()
            self._retry_at = now + 1.0
            return Telemetry(label="ОЖИДАНИЕ iRACING")
