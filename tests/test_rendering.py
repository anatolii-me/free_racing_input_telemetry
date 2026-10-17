from __future__ import annotations

import os
import time
import unittest
from collections import deque
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRectF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from acc_trace.config import Settings  # noqa: E402
from acc_trace.controller import ControllerReader  # noqa: E402
from acc_trace.i18n import status_label  # noqa: E402
from acc_trace.overlay import Overlay  # noqa: E402
from acc_trace.settings_dialog import SettingsDialog  # noqa: E402
from acc_trace.telemetry import Telemetry  # noqa: E402


class OverlayRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_gas_history_remains_visible_beneath_brake_rise(self) -> None:
        overlay = Overlay(Settings(source="demo", avoid_trace_overlap=True))
        overlay.timer.stop()
        now = time.monotonic()
        overlay.current = Telemetry(0, 1, 0, 120, 4, True, "PREVIEW", True)
        overlay._history = deque(
            (now - 3.5 + i / 60, 0.0, max(0.0, min(1.0, (i / 60 - 2.7) / .5)))
            for i in range(211)
        )
        image = overlay.grab().toImage()
        gas = image.pixelColor(300, 122)
        brake = image.pixelColor(300, 128)
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
            for x in range(22, 116)
            for y in range(46, 137)
        )
        self.assertGreater(changed, 50)
        overlay.close()

    def test_wheel_presets_render_distinct_shapes(self) -> None:
        images = []
        for style in ("formula", "sport", "classic"):
            overlay = Overlay(Settings(source="demo", wheel_style=style))
            overlay.timer.stop()
            images.append(overlay.grab().toImage())
            overlay.close()
        for first, second in ((0, 1), (1, 2), (0, 2)):
            changed = sum(images[first].pixelColor(x, y) != images[second].pixelColor(x, y)
                          for x in range(22, 116) for y in range(46, 137))
            self.assertGreater(changed, 100)

    def test_trace_separation_is_opt_in(self) -> None:
        self.assertFalse(Settings().avoid_trace_overlap)
        overlay = Overlay(Settings(source="demo"))
        overlay.timer.stop()
        overlay._history = deque(((0.0, .5, .5), (1.0, .5, .5)))
        chart = QRectF(244, 32, 390, 100)
        gas, brake = overlay._trace_paths(chart, 1.0)
        self.assertEqual(gas.elementAt(0).y, brake.elementAt(0).y)
        overlay.settings.avoid_trace_overlap = True
        gas, brake = overlay._trace_paths(chart, 1.0)
        self.assertLess(gas.elementAt(0).y, brake.elementAt(0).y)
        overlay.close()

    def test_info_controls_move_together_and_save(self) -> None:
        settings = Settings(info_position="bottom", wheel_style="classic", language="en")
        overlay = Overlay(settings)
        overlay.timer.stop()
        settings_rect, close_rect = overlay._controls()
        self.assertGreater(settings_rect.top(), 120)
        self.assertEqual(settings_rect.top(), close_rect.top())
        clicks = []
        overlay.settings_requested.connect(lambda: clicks.append("settings"))
        overlay.close_requested.connect(lambda: clicks.append("close"))
        QTest.mouseClick(overlay, Qt.LeftButton, pos=QPoint(round(settings_rect.center().x()), round(settings_rect.center().y())))
        QTest.mouseClick(overlay, Qt.LeftButton, pos=QPoint(round(close_rect.center().x()), round(close_rect.center().y())))
        self.assertEqual(clicks, ["settings", "close"])
        overlay.close()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            settings.save(path)
            self.assertEqual(Settings.load(path).wheel_style, "classic")
            self.assertEqual(Settings.load(path).info_position, "bottom")
            self.assertEqual(Settings.load(path).language, "en")

    def test_settings_dialog_saves_new_choices(self) -> None:
        dialog = SettingsDialog(Settings(), ControllerReader())
        dialog.wheel_combo.setCurrentIndex(dialog.wheel_combo.findData("sport"))
        dialog.info_combo.setCurrentIndex(dialog.info_combo.findData("bottom"))
        dialog.language_combo.setCurrentIndex(dialog.language_combo.findData("en"))
        dialog.avoid_trace_overlap.setChecked(True)
        dialog._accept()
        self.assertEqual((dialog.result_settings.wheel_style,
                          dialog.result_settings.info_position,
                          dialog.result_settings.language), ("sport", "bottom", "en"))
        self.assertTrue(dialog.result_settings.avoid_trace_overlap)
        dialog.close()

    def test_english_settings_and_status(self) -> None:
        dialog = SettingsDialog(Settings(language="en"), ControllerReader())
        self.assertEqual(dialog.windowTitle(), "Settings · ACC Trace")
        self.assertEqual(dialog.wheel_combo.itemText(0), "Formula")
        self.assertEqual(status_label("en", "ОЖИДАНИЕ РУЛЯ"), "WAITING FOR WHEEL")
        dialog.close()


if __name__ == "__main__":
    unittest.main()
