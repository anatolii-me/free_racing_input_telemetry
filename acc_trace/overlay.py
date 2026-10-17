from __future__ import annotations

import math
import time
from collections import deque

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from .config import Settings
from .telemetry import AccReader, DemoReader, Telemetry
from .controller import ControllerReader


BG = QColor("#111b27")
TEXT = QColor("#f4f7fb")
MUTED = QColor("#8291a1")
GAS = QColor("#83dfb1")
BRAKE = QColor("#ff9586")
STEER = QColor("#a6bdf8")


def font(size: int, weight: QFont.Weight = QFont.Normal) -> QFont:
    result = QFont("Segoe UI Variable", size)
    result.setWeight(weight)
    return result


def paint_icon(size: int = 64) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(BG)
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(QRectF(0, 0, size, size), size * .24, size * .24)
    painter.setPen(QPen(GAS, size * .055, Qt.SolidLine, Qt.RoundCap))
    path = QPainterPath()
    path.moveTo(size * .15, size * .66)
    path.cubicTo(size * .39, size * .66, size * .32, size * .25, size * .57, size * .26)
    path.cubicTo(size * .75, size * .26, size * .71, size * .53, size * .86, size * .53)
    painter.drawPath(path)
    painter.end()
    return pixmap


class Overlay(QWidget):
    settings_requested = Signal()
    position_changed = Signal(int, int)
    context_menu_requested = Signal(QPoint)

    def __init__(self, settings: Settings) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                         Qt.WindowDoesNotAcceptFocus | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_Hover)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)
        self.setWindowTitle("ACC Trace")
        self.setWindowIcon(paint_icon())
        self.setFixedSize(780, 158)
        self.settings = settings
        self.setWindowOpacity(settings.opacity / 100)
        self.acc_reader = AccReader()
        self.controller_reader = ControllerReader()
        self.demo_reader = DemoReader()
        self.current = Telemetry()
        self._history: deque[tuple[float, float, float]] = deque()
        self._smooth_gas = 0.0
        self._smooth_brake = 0.0
        self._last_tick = time.monotonic()
        self._drag_offset: QPoint | None = None
        self._hover_settings = False
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.tick)
        self._next_frame_at = time.monotonic()
        self.apply_settings(settings)

    def apply_settings(self, settings: Settings) -> None:
        previous_source = getattr(self, "settings", settings).source
        self.settings = settings
        self.setWindowOpacity(settings.opacity / 100)
        if settings.source != previous_source:
            self._history.clear()
            self._smooth_gas = self._smooth_brake = 0.0
        self._next_frame_at = time.monotonic() + 1 / settings.update_hz
        self.timer.start(math.ceil(1000 / settings.update_hz))
        self.update()

    def tick(self) -> None:
        now = time.monotonic()
        dt = max(.001, min(.2, now - self._last_tick))
        self._last_tick = now
        if self.settings.source == "demo":
            self.current = self.demo_reader.read()
        else:
            acc = self.acc_reader.read()
            self.current = acc if self.settings.source == "acc" else self.controller_reader.read(self.settings, acc)

        if self.current.connected:
            tau = self.settings.smoothing_ms / 1000
            alpha = 1 if tau == 0 else 1 - math.exp(-dt / tau)
            self._smooth_gas += (self.current.gas - self._smooth_gas) * alpha
            self._smooth_brake += (self.current.brake - self._smooth_brake) * alpha
            self._history.append((now, self._smooth_gas, self._smooth_brake))
        else:
            self._history.clear()
            self._smooth_gas = self._smooth_brake = 0.0
        max_age = 370 / self.settings.graph_speed + .2
        while self._history and now - self._history[0][0] > max_age:
            self._history.popleft()
        self.update()  # polling frequency and paint FPS share one timer
        period = 1 / self.settings.update_hz
        self._next_frame_at += period
        if self._next_frame_at <= time.monotonic():
            self._next_frame_at = time.monotonic() + period
        self.timer.start(max(1, math.ceil((self._next_frame_at - time.monotonic()) * 1000)))

    def closeEvent(self, event) -> None:  # noqa: N802
        self.acc_reader.close()
        self.controller_reader.close()
        super().closeEvent(event)

    def _label(self, p: QPainter, text: str, x: float, y: float, size=10, color=MUTED, weight=QFont.Normal) -> None:
        p.setFont(font(size, weight))
        p.setPen(color)
        p.drawText(QPoint(round(x), round(y)), text)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 38))
        p.drawRoundedRect(QRectF(2, 4, 776, 152), 19, 19)
        p.setBrush(BG)
        p.setPen(QPen(QColor("#354352"), 1))
        p.drawRoundedRect(QRectF(2, 2, 776, 152), 18, 18)

        # Header and connection state.
        self._label(p, "ACC  /  TRACE", 24, 28, 10, QColor("#d4deeb"), QFont.DemiBold)
        status_color = GAS if self.current.connected else QColor("#8795a7")
        p.setPen(Qt.NoPen)
        p.setBrush(status_color)
        p.drawEllipse(QRectF(24, 39, 6, 6))
        self._label(p, self.current.label, 37, 46, 9, MUTED, QFont.DemiBold)
        p.setPen(QPen(QColor("#2a3745"), 1))
        p.drawLine(233, 17, 233, 139)
        p.drawLine(630, 17, 630, 139)

        # Gear, speed and the steering wheel are deliberately sparse.
        if self.settings.show_gear:
            gear = "—" if not self.current.vehicle_available else "R" if self.current.gear == 0 else "N" if self.current.gear == 1 else str(self.current.gear - 1)
            self._label(p, gear, 24, 118, 53, TEXT, QFont.DemiBold)
            self._label(p, "GEAR", 27, 137, 8, MUTED, QFont.DemiBold)
        if self.settings.show_speed:
            speed = "—" if not self.current.vehicle_available else str(round(self.current.speed_kmh))
            self._label(p, speed, 105, 105, 28, TEXT, QFont.DemiBold)
            self._label(p, "КМ/Ч", 107, 124, 9, MUTED, QFont.DemiBold)
        if self.settings.show_steer:
            self._draw_wheel(p, 202, 102, self.current.steer if self.current.connected else 0)

        # Plot background and quiet guide lines.
        chart = QRectF(251, 48, 364, 83)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#172432"))
        p.drawRoundedRect(chart, 10, 10)
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(chart, 10, 10)
        p.setClipPath(clip)
        p.setPen(QPen(QColor("#2c3948"), 1))
        for level in (.25, .5, .75):
            y = chart.bottom() - 7 - level * (chart.height() - 14)
            p.drawLine(QPoint(round(chart.left()), round(y)), QPoint(round(chart.right()), round(y)))
        for x in (chart.right() - 90, chart.right() - 180, chart.right() - 270):
            p.drawLine(QPoint(round(x), round(chart.top())), QPoint(round(x), round(chart.bottom())))
        if len(self._history) > 1:
            gas_path, brake_path = self._trace_paths(chart, time.monotonic())
            p.setBrush(Qt.NoBrush)
            # Draw both glows below both strokes. strokePath never fills the
            # open histories with the chart's background brush.
            for path, color in ((gas_path, GAS), (brake_path, BRAKE)):
                glow = QColor(color)
                glow.setAlpha(36)
                p.strokePath(path, QPen(glow, 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            for path, color in ((gas_path, GAS), (brake_path, BRAKE)):
                p.strokePath(path, QPen(color, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.restore()

        self._label(p, "ИСТОРИЯ НАЖАТИЙ", 252, 29, 9, MUTED, QFont.DemiBold)
        p.setBrush(GAS)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(458, 22, 6, 6))
        self._label(p, "ГАЗ", 469, 29, 9, GAS, QFont.DemiBold)
        p.setBrush(BRAKE)
        p.drawEllipse(QRectF(521, 22, 6, 6))
        self._label(p, "ТОРМОЗ", 532, 29, 9, BRAKE, QFont.DemiBold)
        self._label(p, f"{self.settings.update_hz} ГЦ / FPS", 252, 145, 8, MUTED)
        self._label(p, f"{self.settings.graph_speed} PX/S", 546, 145, 8, MUTED)

        self._draw_bar(p, 649, "ГАЗ", self.current.gas if self.current.connected else 0, GAS)
        self._draw_bar(p, 700, "ТОРМ", self.current.brake if self.current.connected else 0, BRAKE)
        self._draw_settings_icon(p)
        p.end()

    def _trace_paths(self, chart: QRectF, now: float) -> tuple[QPainterPath, QPainterPath]:
        gas_path = QPainterPath()
        brake_path = QPainterPath()
        first = True
        for sample in self._history:
            x = chart.right() - 7 - (now - sample[0]) * self.settings.graph_speed
            height = chart.height() - 14
            gas_y = chart.bottom() - 7 - sample[1] * height
            brake_y = chart.bottom() - 7 - sample[2] * height
            # Two identical values otherwise map to the same pixels. A small,
            # smooth separation makes both histories visible at zero and at
            # transitions without changing the graph's scale.
            near = max(0.0, 1.0 - abs(gas_y - brake_y) / 9.0)
            separation = 3.2 * near * near * (3.0 - 2.0 * near)
            gas_y -= separation
            brake_y += separation
            if first:
                gas_path.moveTo(x, gas_y)
                brake_path.moveTo(x, brake_y)
                first = False
            else:
                gas_path.lineTo(x, gas_y)
                brake_path.lineTo(x, brake_y)
        return gas_path, brake_path

    def _draw_wheel(self, p: QPainter, cx: float, cy: float, steer: float) -> None:
        p.save()
        p.translate(cx, cy)
        p.rotate(steer * self.settings.steering_lock_deg / 2)
        # A restrained, classic three-spoke wheel: warm rim, drilled metal
        # spokes, small hub and a top marker so full turns remain legible.
        p.setPen(QPen(QColor("#6d523f"), 5.5))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(-20, -20, 40, 40))
        p.setPen(QPen(QColor("#c99e73"), 2.5))
        p.drawEllipse(QRectF(-20, -20, 40, 40))
        for angle in (20, 160, 270):
            p.save()
            p.rotate(angle)
            spoke = QPainterPath()
            spoke.moveTo(4, -3.3)
            spoke.lineTo(17.5, -2.2)
            spoke.lineTo(17.5, 2.2)
            spoke.lineTo(4, 3.3)
            spoke.closeSubpath()
            p.setPen(QPen(QColor("#74818e"), .7))
            p.setBrush(QColor("#bdc7ce"))
            p.drawPath(spoke)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#45515f"))
            for radius in (10, 14):
                p.drawEllipse(QRectF(radius - 1.05, -1.05, 2.1, 2.1))
            p.restore()
        p.setPen(QPen(QColor("#e1b98a"), 2.8, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(0, -22, 0, -19)
        p.setBrush(QColor("#263645"))
        p.setPen(QPen(QColor("#d5dde1"), 1.3))
        p.drawEllipse(QRectF(-5.1, -5.1, 10.2, 10.2))
        p.setBrush(QColor("#d5b183"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(-1.3, -1.3, 2.6, 2.6))
        p.restore()

    def _draw_bar(self, p: QPainter, x: float, label: str, value: float, color: QColor) -> None:
        value = max(0, min(1, value))
        self._label(p, f"{round(value * 100):02}", x + 2, 31, 10, TEXT, QFont.DemiBold)
        track = QRectF(x, 40, 28, 79)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#243242"))
        p.drawRoundedRect(track, 7, 7)
        if value > .01:
            height = max(5, (track.height() - 6) * value)
            fill = QRectF(x + 3, track.bottom() - 3 - height, 22, height)
            p.setBrush(color)
            p.drawRoundedRect(fill, 4, 4)
        self._label(p, label, x - (1 if label == "ГАЗ" else 5), 136, 9, MUTED, QFont.DemiBold)

    def _draw_settings_icon(self, p: QPainter) -> None:
        rect = QRectF(742, 12, 25, 25)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#2d3c4e") if self._hover_settings else QColor("#1d2b39"))
        p.drawRoundedRect(rect, 7, 7)
        p.setPen(QPen(QColor("#c6d3df"), 1.5, Qt.SolidLine, Qt.RoundCap))
        for y, knob in ((19, 751), (25, 757), (31, 751)):
            p.drawLine(748, y, 762, y)
            p.setBrush(QColor("#1d2b39"))
            p.drawEllipse(QRectF(knob - 2, y - 2, 4, 4))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            if QRectF(739, 9, 32, 33).contains(event.position()):
                self.settings_requested.emit()
            else:
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        hover = QRectF(739, 9, 32, 33).contains(event.position())
        if hover != self._hover_settings:
            self._hover_settings = hover
            self.setCursor(Qt.PointingHandCursor if hover else Qt.OpenHandCursor)
            self.update()
        if self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None:
            self._drag_offset = None
            self.position_changed.emit(self.x(), self.y())

    def enterEvent(self, event) -> None:  # noqa: N802
        self.setCursor(Qt.OpenHandCursor)

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._hover_settings:
            self._hover_settings = False
            self.update()

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        self.context_menu_requested.emit(event.globalPos())
