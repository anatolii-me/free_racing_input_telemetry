from __future__ import annotations

import math
import socket
import struct
import time

from .telemetry import Telemetry, clamp


# EA's packed Car Telemetry packet (id 6). The 2026 Season Pack sends 24 cars
# with a 59-byte record; the original 2025 format sends 22 60-byte records.
FORMATS = {2025: (1352, 22, 60), 2026: (1448, 24, 59)}
HEADER_SIZE = 29


def parse_f1_25(packet: bytes) -> tuple[int, Telemetry]:
    if len(packet) < HEADER_SIZE:
        raise ValueError("Short F1 packet")
    packet_format = struct.unpack_from("<H", packet)[0]
    layout = FORMATS.get(packet_format)
    if layout is None or len(packet) != layout[0] or packet[6] != 6 or packet[5] != 1:
        raise ValueError("Unsupported F1 Car Telemetry packet")
    _, car_count, car_size = layout
    player = packet[27]
    if player >= car_count:
        raise ValueError("No F1 player car")
    at = HEADER_SIZE + player * car_size
    speed, gas, steer, brake, _clutch, gear = struct.unpack_from("<HfffBb", packet, at)
    if (not all(math.isfinite(value) for value in (gas, steer, brake))
            or speed > 500 or not -1 <= gear <= 10):
        raise ValueError("Invalid F1 player telemetry")
    frame = struct.unpack_from("<I", packet, 23)[0]
    return frame, Telemetry(
        gas=clamp(gas, 0, 1),
        brake=clamp(brake, 0, 1),
        steer=clamp(steer, -1, 1),
        speed_kmh=float(speed),
        gear=gear + 1,
        connected=True,
        label="F1 25 · LIVE",
        vehicle_available=True,
    )


class F125Reader:
    def __init__(self, port: int = 20777) -> None:
        self.port = port
        self._socket: socket.socket | None = None
        self._retry_at = 0.0
        self._last_received = 0.0
        self._last_sample = Telemetry(label="ОЖИДАНИЕ F1 25")

    def configure(self, port: int) -> None:
        if port != self.port:
            self.close()
            self.port = port
            self._retry_at = 0.0

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def read(self) -> Telemetry:
        now = time.monotonic()
        if self._socket is None and now >= self._retry_at:
            sock: socket.socket | None = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setblocking(False)
                sock.bind(("0.0.0.0", self.port))
                self._socket = sock
            except OSError:
                if sock is not None:
                    sock.close()
                self._retry_at = now + 2.0
        if self._socket is None:
            return Telemetry(label="ОЖИДАНИЕ F1 25")
        for _ in range(128):
            try:
                packet, _address = self._socket.recvfrom(4096)
            except BlockingIOError:
                break
            except OSError:
                self.close()
                self._retry_at = now + 2.0
                break
            try:
                _frame, sample = parse_f1_25(packet)
            except (ValueError, struct.error):
                continue
            self._last_sample = sample
            self._last_received = now
        if self._socket is not None and now - self._last_received < 1.5:
            return self._last_sample
        return Telemetry(label="ОЖИДАНИЕ F1 25")
