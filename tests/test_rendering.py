from __future__ import annotations

import os
import time
import unittest
from collections import deque
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from acc_trace.config import Settings  # noqa: E402
from acc_trace.controller import ControllerReader  # noqa: E402
from acc_trace.i18n import status_label  # noqa: E402
from acc_trace.layout import build_layout  # noqa: E402
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
        gas = image.pixelColor(345, 137)
        brake = image.pixelColor(345, 144)
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
        chart = overlay._layout.chart
        gas, brake = overlay._trace_paths(chart, 1.0)
        self.assertEqual(gas.elementAt(0).y, brake.elementAt(0).y)
        overlay.settings.avoid_trace_overlap = True
        gas, brake = overlay._trace_paths(chart, 1.0)
        self.assertLess(gas.elementAt(0).y, brake.elementAt(0).y)
        overlay.close()

    def test_info_controls_move_together_and_save(self) -> None:
        settings = Settings(info_position="bottom", wheel_style="classic", language="en",
                            safe_inset=24, show_pedal_values=False)
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
            self.assertEqual(Settings.load(path).safe_inset, 24)
            self.assertFalse(Settings.load(path).show_pedal_values)

    def test_settings_dialog_saves_new_choices(self) -> None:
        dialog = SettingsDialog(Settings(), ControllerReader())
        dialog.wheel_combo.setCurrentIndex(dialog.wheel_combo.findData("sport"))
        dialog.info_combo.setCurrentIndex(dialog.info_combo.findData("bottom"))
        dialog.language_combo.setCurrentIndex(dialog.language_combo.findData("en"))
        dialog.safe_slider.setValue(24)
        dialog.avoid_trace_overlap.setChecked(True)
        dialog.show_pedal_values.setChecked(False)
        dialog.show_info_bar.setChecked(False)
        dialog.show_history.setChecked(False)
        dialog.show_gas.setChecked(False)
        dialog.show_brake.setChecked(False)
        dialog.forza_port.setValue(5301)
        dialog.f1_port.setValue(20778)
        dialog._accept()
        self.assertEqual((dialog.result_settings.wheel_style,
                          dialog.result_settings.info_position,
                          dialog.result_settings.language), ("sport", "bottom", "en"))
        self.assertTrue(dialog.result_settings.avoid_trace_overlap)
        self.assertEqual(dialog.result_settings.safe_inset, 24)
        self.assertFalse(dialog.result_settings.show_pedal_values)
        self.assertFalse(dialog.result_settings.show_info_bar)
        self.assertFalse(dialog.result_settings.show_history)
        self.assertFalse(dialog.result_settings.show_gas)
        self.assertFalse(dialog.result_settings.show_brake)
        self.assertEqual(dialog.result_settings.forza_port, 5301)
        self.assertEqual(dialog.result_settings.f1_port, 20778)
        self.assertEqual(dialog.result_settings.source, "game")
        dialog.close()

    def test_safe_area_and_separators_share_one_spacing_rule(self) -> None:
        self.assertGreater(build_layout(Settings(safe_inset=8)).wheel_size,
                           build_layout(Settings(safe_inset=30)).wheel_size)
        for inset in (8, 16, 30):
            layout = build_layout(Settings(safe_inset=inset))
            self.assertEqual(layout.safe.left(), inset)
            self.assertEqual(layout.width - layout.safe.right(), inset)
            self.assertEqual(layout.safe.top(), inset)
            self.assertEqual(layout.height - layout.safe.bottom(), inset)
            sections = [layout.wheel, layout.drive, layout.chart_column, layout.pedals]
            for left, divider, right in zip(sections, layout.dividers, sections[1:]):
                self.assertEqual(divider - left.right(), 10)
                self.assertEqual(right.left() - divider, 10)
            self.assertEqual(layout.pedals.right(), layout.safe.right())
            self.assertEqual(layout.gas_track.top(), layout.safe.top())
            self.assertEqual(layout.brake_track.bottom(), layout.safe.bottom())
            self.assertEqual(layout.wheel.center().y(), layout.safe.center().y())
            self.assertEqual(layout.chart.bottom(), layout.safe.bottom())
            bottom = build_layout(Settings(safe_inset=inset, info_position="bottom"))
            self.assertEqual(bottom.chart.top(), bottom.safe.top())

    def test_hidden_inputs_shrink_window_and_remove_unused_dividers(self) -> None:
        overlay = Overlay(Settings(source="demo"))
        overlay.timer.stop()
        full_width = overlay.width()
        graph_width = overlay._layout.chart.width()
        self.assertEqual(len(overlay._layout.dividers), 3)
        overlay.apply_settings(Settings(source="demo", show_steer=False))
        overlay.timer.stop()
        self.assertLess(overlay.width(), full_width)
        self.assertIsNone(overlay._layout.wheel)
        self.assertEqual(len(overlay._layout.dividers), 2)
        self.assertEqual(overlay._layout.chart.width(), graph_width)
        overlay.apply_settings(Settings(source="demo", show_gear=False, show_speed=False))
        overlay.timer.stop()
        self.assertLess(overlay.width(), full_width)
        self.assertIsNone(overlay._layout.drive)
        self.assertEqual(len(overlay._layout.dividers), 2)
        overlay.apply_settings(Settings(source="demo", show_gear=False))
        overlay.timer.stop()
        self.assertLess(overlay.width(), full_width)
        self.assertIsNotNone(overlay._layout.drive)
        overlay.close()

    def test_pedal_value_badges_can_be_hidden_without_changing_bars(self) -> None:
        overlay = Overlay(Settings(source="demo"))
        overlay.timer.stop()
        overlay.current = Telemetry(.63, .28, 0, 120, 4, True, "PREVIEW", True)
        with_values = overlay.grab().toImage()
        gas_track = overlay._layout.gas_track
        overlay.apply_settings(Settings(source="demo", show_pedal_values=False))
        overlay.timer.stop()
        without_values = overlay.grab().toImage()
        center_x = round(gas_track.center().x())
        center_y = round(gas_track.center().y())
        badge_changed = sum(
            with_values.pixelColor(x, y) != without_values.pixelColor(x, y)
            for x in range(center_x - 12, center_x + 12)
            for y in range(center_y - 9, center_y + 9)
        )
        self.assertGreater(badge_changed, 40)
        self.assertEqual(with_values.pixelColor(center_x, round(gas_track.bottom() - 7)),
                         without_values.pixelColor(center_x, round(gas_track.bottom() - 7)))
        overlay.close()

    def test_english_settings_and_status(self) -> None:
        dialog = SettingsDialog(Settings(language="en"), ControllerReader())
        self.assertEqual(dialog.windowTitle(), "Settings · ACC Trace")
        self.assertEqual(dialog.wheel_combo.itemText(0), "Formula")
        self.assertEqual(status_label("en", "ОЖИДАНИЕ РУЛЯ"), "WAITING FOR WHEEL")
        dialog.close()


if __name__ == "__main__":
    unittest.main()
