from __future__ import annotations

import os
import time
import unittest
from collections import deque

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from acc_trace.config import Settings  # noqa: E402
from acc_trace.overlay import Overlay  # noqa: E402
from acc_trace.telemetry import Telemetry  # noqa: E402


class OverlayRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_gas_history_remains_visible_beneath_brake_rise(self) -> None:
        overlay = Overlay(Settings(source="demo"))
        overlay.timer.stop()
        now = time.monotonic()
        overlay.current = Telemetry(0, 1, 0, 120, 4, True, "PREVIEW", True)
        overlay._history = deque(
            (now - 3.5 + i / 60, 0.0, max(0.0, min(1.0, (i / 60 - 2.7) / .5)))
            for i in range(211)
        )
        image = overlay.grab().toImage()
        gas = image.pixelColor(300, 120)
        brake = image.pixelColor(300, 127)
        self.assertGreater(gas.green(), gas.red() + 40)
        self.assertGreater(brake.red(), brake.green() + 40)
        overlay.close()

    def test_steering_lock_changes_wheel_rotation(self) -> None:
        overlay = Overlay(Settings(source="demo", steering_lock_deg=180))
        overlay.timer.stop()
        overlay.current = Telemetry(0, 0, .5, 120, 4, True, "PREVIEW", True)
        small = overlay.grab().toImage()
        overlay.settings.steering_lock_deg = 540
        large = overlay.grab().toImage()
        changed = sum(
            small.pixelColor(x, y) != large.pixelColor(x, y)
            for x in range(178, 226)
            for y in range(78, 126)
        )
        self.assertGreater(changed, 50)
        overlay.close()


if __name__ == "__main__":
    unittest.main()
