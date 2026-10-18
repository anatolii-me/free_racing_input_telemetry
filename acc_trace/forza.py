from __future__ import annotations

import math
import socket
import struct
import time

from .telemetry import Telemetry, clamp


# Horizon Car Dash: 232-byte Sled, 12-byte Horizon extension, then Dash.
PACKET_SIZE = 324


def parse_forza(packet: bytes) -> tuple[int, Telemetry]:
    """Decode the Horizon Data Out Car Dash datagram."""
    if len(packet) != PACKET_SIZE:
        raise ValueError("Expected Forza Horizon Car Dash packet")
    racing, timestamp = struct.unpack_from("<iI", packet)
    if racing != 1:
        raise ValueError("Forza is not driving")
    speed = struct.unpack_from("<f", packet, 256)[0]
    if not math.isfinite(speed) or not 0 <= speed < 300:
        raise ValueError("Invalid Forza speed")
    gas, brake = packet[315], packet[316]
    gear = packet[319]
    steer = struct.unpack_from("<b", packet, 320)[0]
    gear_text = "R" if gear == 0 else "N" if gear == 255 else str(gear)
    return timestamp, Telemetry(
        gas=gas / 255,
        brake=brake / 255,
        steer=clamp(steer / 127, -1, 1),
        speed_kmh=clamp(speed * 3.6, 0, 999),
        gear=gear,
        connected=True,
        label="FH · LIVE",
        vehicle_available=True,
        gear_text=gear_text,
    )


class ForzaReader:
    def __init__(self, port: int = 5300) -> None:
        self.port = port
        self._socket: socket.socket | None = None
        self._retry_at = 0.0
        self._last_received = 0.0
        self._last_sample = Telemetry(label="ОЖИДАНИЕ FH")

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
                # Accept both loopback and the PC's LAN address: some FH builds
                # cannot send Data Out to 127.0.0.1.
                sock.bind(("0.0.0.0", self.port))
                self._socket = sock
            except OSError:
                if sock is not None:
                    sock.close()
                self._retry_at = now + 2.0
        if self._socket is None:
            return Telemetry(label="ОЖИДАНИЕ FH")
        for _ in range(128):
            try:
                packet, _address = self._socket.recvfrom(2048)
            except BlockingIOError:
                break
            except OSError:
                self.close()
                self._retry_at = now + 2.0
                break
            try:
                _timestamp, sample = parse_forza(packet)
            except (ValueError, struct.error):
                continue
            self._last_sample = sample
            self._last_received = now
        if self._socket is not None and now - self._last_received < 1.5:
            return self._last_sample
        return Telemetry(label="ОЖИДАНИЕ FH")
