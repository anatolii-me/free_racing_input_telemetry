from __future__ import annotations

import math
import time
from collections import deque

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from .config import Settings
from .telemetry import AccReader, DemoReader, Telemetry
from .controller import ControllerReader
from .i18n import status_label, tr
from .wheels import draw_wheel


BG = QColor("#111b27")
TEXT = QColor("#f4f7fb")
MUTED = QColor("#8291a1")
GAS = QColor("#83dfb1")
BRAKE = QColor("#ff9586")
STEER = QColor("#a6bdf8")


def font(size: int, weight: QFont.Weight = QFont.Normal) -> QFont:
    result = QFont("Segoe UI", size)
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
    close_requested = Signal()
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
        self.setFixedSize(790, 164)
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
        self._hover_close = False
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.tick)
        self._next_frame_at = time.monotonic()
        self.apply_settings(settings)

    def apply_settings(self, settings: Settings) -> None:
        previous_source = getattr(self, "settings", settings).source
        self.settings = settings
        self._hover_settings = self._hover_close = False
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
        max_age = 377 / self.settings.graph_speed + .2
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

    def _center_text(self, p: QPainter, text: str, rect: QRectF, size: int,
                     color: QColor = TEXT, weight: QFont.Weight = QFont.Normal) -> None:
        p.setFont(font(size, weight))
        p.setPen(color)
        p.drawText(rect, Qt.AlignHCenter | Qt.AlignVCenter, text)

    def _info_y(self) -> float:
        return 20 if self.settings.info_position == "top" else 144

    def _controls(self) -> tuple[QRectF, QRectF]:
        y = self._info_y() - 10
        return QRectF(590, y, 21, 20), QRectF(615, y, 21, 20)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 38))
        p.drawRoundedRect(QRectF(2, 4, 786, 158), 19, 19)
        p.setBrush(BG)
        p.setPen(QPen(QColor("#354352"), 1))
        p.drawRoundedRect(QRectF(2, 2, 786, 158), 18, 18)

        p.setPen(QPen(QColor("#2b3947"), 1))
        for x in (132, 229, 642):
            p.drawLine(QPoint(x, 21), QPoint(x, 143))

        if self.settings.show_steer:
            draw_wheel(p, self.settings.wheel_style, 70, self.height() / 2,
                       98, (self.current.steer if self.current.connected else 0)
                       * self.settings.steering_lock_deg / 2)
        if self.settings.show_gear:
            gear = "—" if not self.current.vehicle_available else "R" if self.current.gear == 0 else "N" if self.current.gear == 1 else str(self.current.gear - 1)
            self._center_text(p, gear, QRectF(143, 24, 75, 50), 41, TEXT, QFont.Bold)
        if self.settings.show_speed:
            speed = "—" if not self.current.vehicle_available else str(round(self.current.speed_kmh))
            self._center_text(p, speed, QRectF(144, 94, 73, 28), 22, TEXT, QFont.DemiBold)
            self._center_text(p, tr(self.settings.language, "kmh"),
                              QRectF(143, 124, 75, 16), 8, MUTED, QFont.DemiBold)
        p.setPen(QPen(QColor("#526273"), 1))
        p.drawLine(154, self.height() // 2, 207, self.height() // 2)

        chart = QRectF(244, 32, 390, 100)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#172432"))
        p.drawRoundedRect(chart, 9, 9)
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(chart, 9, 9)
        p.setClipPath(clip)
        p.setPen(QPen(QColor("#2c3948"), 1))
        for level in (.25, .5, .75):
            y = chart.bottom() - 7 - level * (chart.height() - 14)
            p.drawLine(QPoint(round(chart.left()), round(y)), QPoint(round(chart.right()), round(y)))
        for x in (chart.right() - 95, chart.right() - 190, chart.right() - 285):
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
        self._draw_bar(p, 662, self.current.gas if self.current.connected else 0, GAS)
        self._draw_bar(p, 718, self.current.brake if self.current.connected else 0, BRAKE)
        self._draw_info_rail(p)
        p.end()

    def _draw_info_rail(self, p: QPainter) -> None:
        y = self._info_y()
        status_color = GAS if self.current.connected else MUTED
        p.setPen(Qt.NoPen)
        p.setBrush(status_color)
        p.drawEllipse(QRectF(244, y - 3, 6, 6))
        p.setFont(font(8, QFont.DemiBold))
        p.setPen(QColor("#d6e0e9"))
        label = status_label(self.settings.language, self.current.label)
        label = QFontMetrics(p.font()).elidedText(label, Qt.ElideRight, 112)
        p.drawText(QPoint(256, round(y + 4)), label)
        p.setPen(Qt.NoPen)
        p.setBrush(GAS)
        p.drawEllipse(QRectF(376, y - 3, 6, 6))
        self._label(p, tr(self.settings.language, "gas").upper(), 386, y + 4, 8, GAS, QFont.DemiBold)
        p.setBrush(BRAKE)
        p.drawEllipse(QRectF(421, y - 3, 6, 6))
        self._label(p, tr(self.settings.language, "brake").upper(), 431, y + 4, 8, BRAKE, QFont.DemiBold)
        self._label(p, f"{self.settings.update_hz} FPS", 487, y + 4, 8, MUTED, QFont.DemiBold)
        self._label(p, f"{self.settings.graph_speed} PX/S", 537, y + 4, 8, MUTED, QFont.DemiBold)
        settings_rect, close_rect = self._controls()
        self._draw_control(p, settings_rect, "settings", self._hover_settings)
        self._draw_control(p, close_rect, "close", self._hover_close)

    def _trace_paths(self, chart: QRectF, now: float) -> tuple[QPainterPath, QPainterPath]:
        gas_path = QPainterPath()
        brake_path = QPainterPath()
        first = True
        for sample in self._history:
            x = chart.right() - 7 - (now - sample[0]) * self.settings.graph_speed
            height = chart.height() - 14
            gas_y = chart.bottom() - 7 - sample[1] * height
            brake_y = chart.bottom() - 7 - sample[2] * height
            if self.settings.avoid_trace_overlap:
                # Optionally separate near-equal values so both traces remain visible.
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

    def _draw_bar(self, p: QPainter, x: float, value: float, color: QColor) -> None:
        value = max(0, min(1, value))
        self._center_text(p, f"{round(value * 100):02}", QRectF(x - 5, 16, 38, 18),
                          10, TEXT, QFont.DemiBold)
        track = QRectF(x, 37, 28, 110)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#243242"))
        p.drawRoundedRect(track, 7, 7)
        if value > .01:
            height = max(5, (track.height() - 6) * value)
            fill = QRectF(x + 3, track.bottom() - 3 - height, 22, height)
            p.setBrush(color)
            p.drawRoundedRect(fill, 4, 4)

    def _draw_control(self, p: QPainter, rect: QRectF, kind: str, hover: bool) -> None:
        if hover:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#304254"))
            p.drawRoundedRect(rect, 5, 5)
        cx, cy = rect.center().x(), rect.center().y()
        p.setPen(QPen(QColor("#c5d3df"), 1.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        if kind == "close":
            p.drawLine(QPoint(round(cx - 3.5), round(cy - 3.5)), QPoint(round(cx + 3.5), round(cy + 3.5)))
            p.drawLine(QPoint(round(cx + 3.5), round(cy - 3.5)), QPoint(round(cx - 3.5), round(cy + 3.5)))
        else:
            for angle in range(0, 360, 45):
                radians = math.radians(angle)
                p.drawLine(QPoint(round(cx + 4.7 * math.cos(radians)), round(cy + 4.7 * math.sin(radians))),
                           QPoint(round(cx + 6.3 * math.cos(radians)), round(cy + 6.3 * math.sin(radians))))
            p.drawEllipse(QRectF(cx - 4.4, cy - 4.4, 8.8, 8.8))
            p.drawEllipse(QRectF(cx - 1.3, cy - 1.3, 2.6, 2.6))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            settings_rect, close_rect = self._controls()
            if settings_rect.contains(event.position()):
                self.settings_requested.emit()
            elif close_rect.contains(event.position()):
                self.close_requested.emit()
            else:
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        settings_rect, close_rect = self._controls()
        hover_settings = settings_rect.contains(event.position())
        hover_close = close_rect.contains(event.position())
        if (hover_settings, hover_close) != (self._hover_settings, self._hover_close):
            self._hover_settings, self._hover_close = hover_settings, hover_close
            self.setCursor(Qt.PointingHandCursor if hover_settings or hover_close else Qt.OpenHandCursor)
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
        if self._hover_settings or self._hover_close:
            self._hover_settings = self._hover_close = False
            self.update()

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        self.context_menu_requested.emit(event.globalPos())
