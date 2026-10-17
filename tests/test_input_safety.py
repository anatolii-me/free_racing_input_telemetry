from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from acc_trace.config import Settings  # noqa: E402
from acc_trace.controller import ControllerReader, DeviceInfo  # noqa: E402
from acc_trace.overlay import Overlay  # noqa: E402
from acc_trace.settings_dialog import SettingsDialog  # noqa: E402
from acc_trace.telemetry import Telemetry  # noqa: E402


class FakeJoystickApi:
    def __init__(self) -> None:
        self.scans = 0
        self.reads = 0

    def devices(self) -> list[DeviceInfo]:
        self.scans += 1
        return [DeviceInfo("2", "Test wheel", ((0, 100),) * 6, frozenset(range(6)))]

    def read_raw(self, device_id: int) -> tuple[int, ...]:
        self.reads += 1
        assert device_id == 2
        return (75, 50, 100, 0, 50, 50)


class InputSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_acc_settings_never_scan_wheel_until_direct_mode_selected(self) -> None:
        api = FakeJoystickApi()
        dialog = SettingsDialog(Settings(source="acc"), ControllerReader(api))
        self.assertEqual(api.scans, 0)
        self.assertEqual(api.reads, 0)
        dialog.source_combo.setCurrentIndex(dialog.source_combo.findData("controller"))
        self.assertEqual(api.scans, 1)
        self.assertEqual(api.reads, 0)
        dialog.close()

    def test_acc_overlay_never_opens_controller_backend(self) -> None:
        overlay = Overlay(Settings(source="acc"))
        overlay.timer.stop()

        def forbidden_backend() -> None:
            self.fail("ACC source accessed the wheel")

        overlay.controller_reader._backend = forbidden_backend
        overlay.acc_reader.read = lambda: Telemetry(.5, .2, .1, 100, 3, True, "ACC", True)
        overlay.tick()
        overlay.timer.stop()
        self.assertTrue(overlay.windowFlags() & Qt.WindowDoesNotAcceptFocus)
        self.assertTrue(overlay.testAttribute(Qt.WA_ShowWithoutActivating))
        overlay.close()

    def test_direct_axes_are_read_without_device_acquisition(self) -> None:
        api = FakeJoystickApi()
        reader = ControllerReader(api)
        sample = reader.read(Settings(source="controller", gas_axis=2, brake_axis=3,
                                      steer_axis=0), Telemetry(speed_kmh=90, gear=4))
        self.assertEqual(api.scans, 1)
        self.assertEqual(api.reads, 1)
        self.assertAlmostEqual(sample.gas, 1)
        self.assertAlmostEqual(sample.brake, 0)
        self.assertAlmostEqual(sample.steer, .5)
        self.assertEqual(sample.speed_kmh, 90)
        reader.close()


if __name__ == "__main__":
    unittest.main()
