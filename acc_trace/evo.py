from __future__ import annotations

import math
import struct
from dataclasses import replace

from .telemetry import AccReader, Telemetry, clamp, parse_physics


MAP_NAME = r"Local\acevo_pmf_physics"


def parse_evo(data: bytes, steering_lock_deg: int = 540) -> tuple[int, Telemetry]:
    """Read AC EVO's AC-compatible physics prefix; steerAngle is in radians."""
    packet, sample = parse_physics(data)
    angle = struct.unpack_from("<f", data, 24)[0]
    half_lock = math.radians(max(180, steering_lock_deg) / 2)
    return packet, replace(sample,
                           steer=clamp(angle / half_lock, -1, 1),
                           label="AC EVO · LIVE")


class EvoReader(AccReader):
    def __init__(self, steering_lock_deg: int = 540) -> None:
        super().__init__(MAP_NAME, "ОЖИДАНИЕ AC EVO")
        self.steering_lock_deg = steering_lock_deg

    def configure(self, steering_lock_deg: int) -> None:
        self.steering_lock_deg = steering_lock_deg

    def _parse(self, data: bytes) -> tuple[int, Telemetry]:
        return parse_evo(data, self.steering_lock_deg)
