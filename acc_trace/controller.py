from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes
from dataclasses import dataclass

from .config import Settings
from .telemetry import Telemetry, clamp


AXIS_NAMES = ("X", "Y", "Z", "R", "U", "V")
JOY_RETURNALL = 0x00FF
JOYCAPS_HASZ = 0x0001
JOYCAPS_HASR = 0x0002
JOYCAPS_HASU = 0x0004
JOYCAPS_HASV = 0x0008


class JOYINFOEX(ctypes.Structure):
    _fields_ = [(name, wintypes.DWORD) for name in (
        "dwSize", "dwFlags", "dwXpos", "dwYpos", "dwZpos", "dwRpos",
        "dwUpos", "dwVpos", "dwButtons", "dwButtonNumber", "dwPOV",
        "dwReserved1", "dwReserved2",
    )]


class JOYCAPSW(ctypes.Structure):
    _fields_ = [
        ("wMid", wintypes.WORD),
        ("wPid", wintypes.WORD),
        ("szPname", ctypes.c_wchar * 32),
        *[(name, wintypes.UINT) for name in (
            "wXmin", "wXmax", "wYmin", "wYmax", "wZmin", "wZmax",
            "wNumButtons", "wPeriodMin", "wPeriodMax", "wRmin", "wRmax",
            "wUmin", "wUmax", "wVmin", "wVmax", "wCaps", "wMaxAxes",
            "wNumAxes", "wMaxButtons",
        )],
        ("szRegKey", ctypes.c_wchar * 32),
        ("szOEMVxD", ctypes.c_wchar * 260),
    ]


@dataclass(frozen=True)
class DeviceInfo:
    identifier: str
    name: str
    ranges: tuple[tuple[int, int], ...]
    available_axes: frozenset[int]


class WinMMJoystickApi:
    """Read-only WinMM polling. Never captures, acquires or sends FFB commands."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("WinMM is available only on Windows")
        dll = ctypes.WinDLL("winmm", use_last_error=True)
        self._count = dll.joyGetNumDevs
        self._count.argtypes = ()
        self._count.restype = wintypes.UINT
        self._caps = dll.joyGetDevCapsW
        self._caps.argtypes = (ctypes.c_size_t, ctypes.POINTER(JOYCAPSW), wintypes.UINT)
        self._caps.restype = wintypes.UINT
        self._position = dll.joyGetPosEx
        self._position.argtypes = (wintypes.UINT, ctypes.POINTER(JOYINFOEX))
        self._position.restype = wintypes.UINT

    def read_raw(self, device_id: int) -> tuple[int, ...] | None:
        state = JOYINFOEX()
        state.dwSize = ctypes.sizeof(state)
        state.dwFlags = JOY_RETURNALL
        if self._position(device_id, ctypes.byref(state)) != 0:
            return None
        return (state.dwXpos, state.dwYpos, state.dwZpos,
                state.dwRpos, state.dwUpos, state.dwVpos)

    def devices(self) -> list[DeviceInfo]:
        found: list[DeviceInfo] = []
        for device_id in range(min(self._count(), 16)):
            if self.read_raw(device_id) is None:
                continue
            caps = JOYCAPSW()
            if self._caps(device_id, ctypes.byref(caps), ctypes.sizeof(caps)) != 0:
                continue
            axes = {0, 1}
            for index, flag in ((2, JOYCAPS_HASZ), (3, JOYCAPS_HASR),
                                (4, JOYCAPS_HASU), (5, JOYCAPS_HASV)):
                if caps.wCaps & flag:
                    axes.add(index)
            ranges = tuple((getattr(caps, f"w{name}min"), getattr(caps, f"w{name}max"))
                           for name in AXIS_NAMES)
            found.append(DeviceInfo(str(device_id), caps.szPname or f"Устройство {device_id}",
                                    ranges, frozenset(axes)))
        return found


class ControllerReader:
    def __init__(self, api: WinMMJoystickApi | None = None) -> None:
        self._api = api
        self._known: dict[str, DeviceInfo] = {}
        self._retry_at = 0.0

    def _backend(self) -> WinMMJoystickApi | None:
        if self._api is None and os.name == "nt":
            self._api = WinMMJoystickApi()
        return self._api

    def devices(self) -> list[tuple[str, str]]:
        backend = self._backend()
        if backend is None:
            return []
        found = backend.devices()
        self._known = {device.identifier: device for device in found}
        return [(device.identifier, device.name) for device in found]

    def axis_samples(self, identifier: str = "") -> dict[str, dict[int, float]]:
        """Normalized snapshots for axis learning; an empty id checks every device."""
        backend = self._backend()
        if backend is None:
            return {}
        self.devices()
        result: dict[str, dict[int, float]] = {}
        for device in self._known.values():
            if identifier and identifier != device.identifier:
                continue
            raw = backend.read_raw(int(device.identifier))
            if raw is None:
                continue
            result[device.identifier] = {
                index: clamp((raw[index] - device.ranges[index][0]) /
                             max(1, device.ranges[index][1] - device.ranges[index][0]), 0, 1)
                for index in device.available_axes
            }
        return result

    def close(self) -> None:
        # WinMM polling holds no acquisition or device handle.
        self._known.clear()

    def _selected(self, identifier: str) -> DeviceInfo | None:
        needs_scan = not self._known or (identifier.isdecimal() and identifier not in self._known)
        if needs_scan and time.monotonic() >= self._retry_at:
            self.devices()
            self._retry_at = time.monotonic() + 1.0
        if identifier.isdecimal():
            return self._known.get(identifier)
        # An empty setting picks the first device. Old SDL GUIDs migrate here.
        return next(iter(self._known.values()), None)

    def read(self, settings: Settings, acc: Telemetry) -> Telemetry:
        backend = self._backend()
        if backend is None:
            return Telemetry(speed_kmh=acc.speed_kmh, gear=acc.gear, label="РУЛЬ: ТОЛЬКО WINDOWS")
        device = self._selected(settings.controller_guid)
        if device is None:
            label = "ОЖИДАНИЕ ИГРЫ / РУЛЯ" if settings.source == "auto" else "ОЖИДАНИЕ РУЛЯ"
            return Telemetry(speed_kmh=acc.speed_kmh, gear=acc.gear, label=label)
        raw = backend.read_raw(int(device.identifier))
        if raw is None:
            self._known.clear()
            self._retry_at = time.monotonic() + 1.0
            return Telemetry(speed_kmh=acc.speed_kmh, gear=acc.gear, label="ОЖИДАНИЕ РУЛЯ")
        chosen = (settings.gas_axis, settings.brake_axis, settings.steer_axis)
        if any(index not in device.available_axes for index in chosen):
            return Telemetry(speed_kmh=acc.speed_kmh, gear=acc.gear, label="НАСТРОЙТЕ ОСИ")

        def axis(index: int) -> float:
            low, high = device.ranges[index]
            return clamp(2 * (raw[index] - low) / max(1, high - low) - 1, -1, 1)

        gas_axis = axis(settings.gas_axis)
        brake_axis = axis(settings.brake_axis)
        gas = (1 - gas_axis) / 2 if settings.invert_gas else (gas_axis + 1) / 2
        brake = (1 - brake_axis) / 2 if settings.invert_brake else (brake_axis + 1) / 2
        steer = -axis(settings.steer_axis) if settings.invert_steer else axis(settings.steer_axis)
        return Telemetry(gas, brake, steer, acc.speed_kmh, acc.gear, True,
                         "РУЛЬ · LIVE", acc.connected)


class AxisDetector:
    """Select a dominant intentional movement above the resting baseline."""

    def __init__(self, baseline: dict[str, dict[int, float]]) -> None:
        self.baseline = baseline
        self._candidate: tuple[str, int] | None = None
        self._stable = 0

    def feed(self, samples: dict[str, dict[int, float]]) -> tuple[str, int, bool] | None:
        changes: list[tuple[float, str, int, bool]] = []
        for device_id, axes in samples.items():
            for index, value in axes.items():
                start = self.baseline.get(device_id, {}).get(index)
                if start is not None:
                    delta = value - start
                    changes.append((abs(delta), device_id, index, delta < 0))
        changes.sort(reverse=True)
        if not changes or changes[0][0] < .22 or (len(changes) > 1 and changes[0][0] < changes[1][0] * 1.5):
            self._candidate = None
            self._stable = 0
            return None
        _, device_id, index, inverted = changes[0]
        candidate = (device_id, index)
        self._stable = self._stable + 1 if candidate == self._candidate else 1
        self._candidate = candidate
        return (device_id, index, inverted) if self._stable >= 2 else None
