from __future__ import annotations

import os
import struct
import unittest
import json
import socket
import math
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from acc_trace.config import Settings  # noqa: E402
from acc_trace.controller import AxisDetector  # noqa: E402
from acc_trace.forza import ForzaReader, parse_forza  # noqa: E402
from acc_trace.f1_25 import F125Reader, FORMATS, HEADER_SIZE, parse_f1_25  # noqa: E402
from acc_trace.evo import EvoReader, MAP_NAME, parse_evo  # noqa: E402
from acc_trace.iracing import parse_iracing  # noqa: E402
from acc_trace.layout import build_layout  # noqa: E402
from acc_trace.lmu import MAP_SIZE, TELEMETRY_OFFSET, VEHICLE_SIZE, parse_lmu  # noqa: E402
from acc_trace.overlay import Overlay  # noqa: E402
from acc_trace.settings_dialog import SettingsDialog  # noqa: E402
from acc_trace.telemetry import Telemetry  # noqa: E402


def iracing_snapshot() -> bytes:
    names = ("Throttle", "Brake", "SteeringWheelAngle", "Speed", "Gear", "SteeringWheelAngleMax")
    data = bytearray(1200)
    struct.pack_into("<10i", data, 0, 2, 1, 60, 0, 0, 0, len(names), 112, 1, 24)
    struct.pack_into("<3i", data, 48, 7, 1000, 7)
    for index, name in enumerate(names):
        at = 112 + index * 144
        struct.pack_into("<3i", data, at, 2 if name == "Gear" else 4, index * 4, 1)
        data[at + 16:at + 16 + len(name)] = name.encode("ascii")
    struct.pack_into("<4fif", data, 1000, .75, .25, 1.0, 25.0, 3, 2.0)
    return bytes(data)


class NewFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_compact_chart_uses_safe_height_and_hover_controls_work(self) -> None:
        settings = Settings(source="demo", show_info_bar=False)
        layout = build_layout(settings)
        self.assertEqual(layout.chart, layout.chart_column)
        self.assertEqual(layout.chart.top(), layout.safe.top())
        self.assertEqual(layout.chart.bottom(), layout.safe.bottom())
        overlay = Overlay(settings)
        overlay.timer.stop()
        overlay.current = Telemetry(connected=True)
        hidden = overlay.grab().toImage()
        overlay._pointer_inside = True
        shown = overlay.grab().toImage()
        button = layout.settings_button.center()
        self.assertNotEqual(hidden.pixelColor(round(button.x()), round(button.y())),
                            shown.pixelColor(round(button.x()), round(button.y())))
        rail_x = round(layout.chart.left() + 25)
        rail_y = round(layout.rail_y + 8)
        self.assertNotEqual(hidden.pixelColor(rail_x, rail_y), shown.pixelColor(rail_x, rail_y))
        clicked = []
        overlay.settings_requested.connect(lambda: clicked.append(True))
        QTest.mouseClick(overlay, Qt.LeftButton, pos=QPoint(round(button.x()), round(button.y())))
        self.assertEqual(clicked, [True])
        overlay.close()

    def test_axis_detector_ignores_noise_and_finds_dominant_device(self) -> None:
        detector = AxisDetector({"0": {0: .5, 1: .9}, "2": {0: .5, 3: 1.0}})
        self.assertIsNone(detector.feed({"0": {0: .53, 1: .9}, "2": {0: .5, 3: .98}}))
        moved = {"0": {0: .54, 1: .9}, "2": {0: .5, 3: .4}}
        self.assertIsNone(detector.feed(moved))
        self.assertEqual(detector.feed(moved), ("2", 3, True))

    def test_axis_learning_sets_device_axis_and_pedal_direction(self) -> None:
        class FakeController:
            moved = False

            def devices(self):
                return [("2", "Test pedals")]

            def axis_samples(self, identifier=""):
                return {"2": {0: .5, 3: .2 if self.moved else 1.0}}

        controller = FakeController()
        dialog = SettingsDialog(Settings(source="controller"), controller)
        dialog._start_axis_learning("brake")
        controller.moved = True
        dialog._poll_axis()
        dialog._poll_axis()
        self.assertEqual(dialog.device_combo.currentData(), "2")
        self.assertEqual(dialog.axes["brake"].currentData(), 3)
        self.assertTrue(dialog.inverts["brake"].isChecked())
        dialog.close()

    def test_iracing_parser_reads_and_converts_sdk_units(self) -> None:
        tick, sample = parse_iracing(iracing_snapshot())
        self.assertEqual(tick, 7)
        self.assertAlmostEqual(sample.gas, .75)
        self.assertAlmostEqual(sample.brake, .25)
        self.assertAlmostEqual(sample.steer, .5)
        self.assertAlmostEqual(sample.speed_kmh, 90)
        self.assertEqual(sample.gear, 4)
        with self.assertRaises(ValueError):
            parse_iracing(bytes(112))

    def test_forza_horizon_car_dash_packet_and_udp_reader(self) -> None:
        packet = bytearray(324)
        struct.pack_into("<iI", packet, 0, 1, 42)
        struct.pack_into("<f", packet, 256, 25.0)
        packet[315], packet[316], packet[319] = 204, 102, 3
        struct.pack_into("<b", packet, 320, -64)
        tick, sample = parse_forza(packet)
        self.assertEqual(tick, 42)
        self.assertAlmostEqual(sample.gas, .8)
        self.assertAlmostEqual(sample.brake, .4)
        self.assertAlmostEqual(sample.steer, -64 / 127)
        self.assertAlmostEqual(sample.speed_kmh, 90)
        self.assertEqual(sample.gear_text, "3")
        self.assertEqual(sample.label, "FH · LIVE")
        with self.assertRaises(ValueError):
            parse_forza(packet[:-1])
        reader = ForzaReader(0)
        try:
            self.assertFalse(reader.read().connected)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                sender.sendto(packet, ("127.0.0.1", reader._socket.getsockname()[1]))
            self.assertTrue(reader.read().connected)
        finally:
            reader.close()

    def test_lmu_native_shared_memory_player_car(self) -> None:
        data = bytearray(MAP_SIZE)
        data[TELEMETRY_OFFSET:TELEMETRY_OFFSET + 3] = bytes((2, 1, 1))
        car = TELEMETRY_OFFSET + 4 + VEHICLE_SIZE
        struct.pack_into("<d", data, car + 12, 10.25)
        struct.pack_into("<3d", data, car + 184, 3.0, 4.0, 0.0)
        struct.pack_into("<i", data, car + 352, 5)
        struct.pack_into("<3d", data, car + 388, .7, .3, -.25)
        elapsed, sample = parse_lmu(data)
        self.assertEqual(elapsed, 10.25)
        self.assertAlmostEqual(sample.speed_kmh, 18)
        self.assertAlmostEqual(sample.gas, .7)
        self.assertAlmostEqual(sample.brake, .3)
        self.assertAlmostEqual(sample.steer, -.25)
        self.assertEqual(sample.gear, 6)
        self.assertEqual(sample.label, "LMU · LIVE")
        data[TELEMETRY_OFFSET + 2] = 0
        with self.assertRaises(ValueError):
            parse_lmu(data)

    def test_ac_evo_physics_prefix_and_radian_steering(self) -> None:
        data = struct.pack("<ifffiiff", 7, .75, .25, 20.0, 4, 6000,
                           math.pi / 2, 108.0)
        packet, sample = parse_evo(data, steering_lock_deg=360)
        self.assertEqual(packet, 7)
        self.assertAlmostEqual(sample.gas, .75)
        self.assertAlmostEqual(sample.brake, .25)
        self.assertAlmostEqual(sample.steer, .5)
        self.assertEqual(sample.gear, 4)
        self.assertEqual(sample.label, "AC EVO · LIVE")
        reader = EvoReader()
        self.assertEqual(reader.map_name, MAP_NAME)
        reader.configure(360)
        self.assertAlmostEqual(reader._parse(data)[1].steer, .5)

    def test_f1_25_2025_and_2026_car_telemetry_packets(self) -> None:
        for udp_format, (size, _cars, stride) in FORMATS.items():
            with self.subTest(udp_format=udp_format):
                packet = bytearray(size)
                struct.pack_into("<H", packet, 0, udp_format)
                packet[5], packet[6], packet[27] = 1, 6, 2
                struct.pack_into("<I", packet, 23, 42)
                struct.pack_into("<HfffBb", packet, HEADER_SIZE + 2 * stride,
                                 287, .8, -.25, .4, 0, 5)
                frame, sample = parse_f1_25(packet)
                self.assertEqual(frame, 42)
                self.assertEqual(sample.speed_kmh, 287)
                self.assertAlmostEqual(sample.gas, .8)
                self.assertAlmostEqual(sample.brake, .4)
                self.assertAlmostEqual(sample.steer, -.25)
                self.assertEqual(sample.gear, 6)
                self.assertEqual(sample.label, "F1 25 · LIVE")
                packet[6] = 7
                with self.assertRaises(ValueError):
                    parse_f1_25(packet)

    def test_f1_udp_reader_receives_matching_port(self) -> None:
        packet = bytearray(FORMATS[2025][0])
        struct.pack_into("<H", packet, 0, 2025)
        packet[5], packet[6], packet[27] = 1, 6, 0
        struct.pack_into("<HfffBb", packet, HEADER_SIZE, 120, .5, .1, .2, 0, 3)
        reader = F125Reader(0)
        try:
            self.assertFalse(reader.read().connected)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                sender.sendto(packet, ("127.0.0.1", reader._socket.getsockname()[1]))
            self.assertEqual(reader.read().label, "F1 25 · LIVE")
        finally:
            reader.close()

    def test_each_vertical_section_changes_window_width(self) -> None:
        baseline = build_layout(Settings())
        for field, rect in (("show_history", "chart"), ("show_gas", "gas_track"),
                            ("show_brake", "brake_track"), ("show_steer", "wheel"),
                            ("show_speed", "drive"), ("show_gear", "drive")):
            settings = Settings(**{field: False})
            layout = build_layout(settings)
            self.assertLess(layout.width, baseline.width, field)
            if field not in ("show_speed", "show_gear"):
                self.assertIsNone(getattr(layout, rect), field)
        empty = build_layout(Settings(show_history=False, show_gas=False,
                                      show_brake=False, show_steer=False,
                                      show_speed=False, show_gear=False))
        self.assertEqual(empty.width, 128)
        self.assertIsNone(empty.chart)
        self.assertGreaterEqual(empty.close_button.left(), 0)
        self.assertLessEqual(empty.close_button.right(), empty.width)

    def test_game_prefers_ac_without_controller_polling(self) -> None:
        overlay = Overlay(Settings(source="game"))
        overlay.timer.stop()
        overlay.acc_reader.read = lambda: Telemetry(.6, .2, .1, 80, 3, True, "AC / ACC · LIVE", True)
        overlay.iracing_reader.read = lambda: self.fail("iRacing should not override AC / ACC")
        overlay.controller_reader.read = lambda *_: self.fail("Live game should not poll wheel")
        overlay.tick()
        overlay.timer.stop()
        self.assertAlmostEqual(overlay.current.gas, .6)
        overlay.close()

    def test_game_uses_iracing_when_ac_is_absent(self) -> None:
        overlay = Overlay(Settings(source="game"))
        overlay.timer.stop()
        overlay.acc_reader.read = lambda: Telemetry()
        overlay.evo_reader.read = lambda: Telemetry()
        overlay.iracing_reader.read = lambda: Telemetry(.4, .1, 0, 90, 4, True, "iRacing · LIVE", True)
        overlay.controller_reader.read = lambda *_: self.fail("Live game should not poll wheel")
        overlay.tick()
        overlay.timer.stop()
        self.assertEqual(overlay.current.label, "iRacing · LIVE")
        overlay.close()

    def test_game_mode_detects_lmu_and_fh_without_touching_device(self) -> None:
        for selected in ("lmu", "forza"):
            with self.subTest(selected=selected):
                overlay = Overlay(Settings(source="game"))
                overlay.timer.stop()
                overlay.acc_reader.read = lambda: Telemetry()
                overlay.evo_reader.read = lambda: Telemetry()
                overlay.iracing_reader.read = lambda: Telemetry()
                overlay.lmu_reader.read = lambda: Telemetry()
                overlay.forza_reader.read = lambda: Telemetry()
                overlay.f1_reader.read = lambda: Telemetry()
                reader = getattr(overlay, f"{selected}_reader")
                reader.read = lambda name=selected: Telemetry(
                    connected=True, label="LMU · LIVE" if name == "lmu" else "FH · LIVE")
                overlay.controller_reader.read = lambda *_: self.fail("Game mode polled device")
                overlay.tick()
                overlay.timer.stop()
                self.assertEqual(overlay.current.label,
                                 "LMU · LIVE" if selected == "lmu" else "FH · LIVE")
                overlay.close()

    def test_game_mode_detects_ac_evo_and_f1(self) -> None:
        for selected, label in (("evo", "AC EVO · LIVE"), ("f1", "F1 25 · LIVE")):
            with self.subTest(selected=selected):
                overlay = Overlay(Settings(source="game"))
                overlay.timer.stop()
                for name in ("acc", "evo", "iracing", "lmu", "forza", "f1"):
                    getattr(overlay, f"{name}_reader").read = lambda: Telemetry()
                getattr(overlay, f"{selected}_reader").read = (
                    lambda live_label=label: Telemetry(connected=True, label=live_label))
                overlay.controller_reader.read = lambda *_: self.fail("Game mode polled device")
                overlay.tick()
                overlay.timer.stop()
                self.assertEqual(overlay.current.label, label)
                overlay.close()

    def test_legacy_acc_default_migrates_to_game(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(json.dumps({"source": "acc", "graph_speed": 105}), encoding="utf-8")
            migrated = Settings.load(path)
            self.assertEqual(migrated.source, "game")
            self.assertEqual(migrated.graph_speed, 105)


if __name__ == "__main__":
    unittest.main()
