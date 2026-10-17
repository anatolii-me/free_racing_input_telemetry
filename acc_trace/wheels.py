from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen


INK = QColor("#101923")
RIM = QColor("#263747")
METAL = QColor("#718295")
HIGHLIGHT = QColor("#b6c5d3")
AMBER = QColor("#e2b977")
MINT = QColor("#83dfb1")


def _polygon(points: tuple[tuple[float, float], ...]) -> QPainterPath:
    path = QPainterPath()
    path.moveTo(*points[0])
    for point in points[1:]:
        path.lineTo(*point)
    path.closeSubpath()
    return path


def draw_wheel(p: QPainter, style: str, cx: float, cy: float, size: float, degrees: float) -> None:
    """Draw three related wheel silhouettes on a shared 100-unit canvas."""
    p.save()
    p.translate(cx, cy)
    p.rotate(degrees)
    p.scale(size / 100, size / 100)
    p.setRenderHint(QPainter.Antialiasing)
    if style == "formula":
        _formula(p)
    elif style == "sport":
        _sport(p)
    else:
        _classic(p)
    p.restore()


def _formula(p: QPainter) -> None:
    body = QPainterPath()
    body.moveTo(-32, -34)
    body.cubicTo(-40, -34, -46, -25, -46, -13)
    body.lineTo(-44, 25)
    body.cubicTo(-44, 33, -38, 38, -32, 35)
    body.lineTo(-27, 22)
    body.cubicTo(-24, 16, -22, 20, -20, 25)
    body.cubicTo(-15, 34, -10, 36, 0, 36)
    body.cubicTo(10, 36, 15, 34, 20, 25)
    body.cubicTo(22, 20, 24, 16, 27, 22)
    body.lineTo(32, 35)
    body.cubicTo(38, 38, 44, 33, 44, 25)
    body.lineTo(46, -13)
    body.cubicTo(46, -25, 40, -34, 32, -34)
    body.closeSubpath()
    p.setPen(QPen(QColor("#334657"), 1.5))
    p.setBrush(INK)
    p.drawPath(body)

    # Broad grips and a flat bridge give the wheel its formula silhouette.
    p.setPen(QPen(RIM, 7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(-40, -16, -38, 26)
    p.drawLine(40, -16, 38, 26)
    p.setPen(QPen(METAL, 1.2, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(-28, -31, 28, -31)

    p.setPen(QPen(METAL, 1.2))
    p.setBrush(QColor("#172534"))
    p.drawRoundedRect(QRectF(-22, -19, 44, 32), 3, 3)
    p.setPen(QPen(QColor("#465e70"), 1))
    p.drawLine(-16, 8, 16, 8)

    p.setPen(Qt.NoPen)
    for x in range(-15, 16, 5):
        p.setBrush(MINT if abs(x) <= 5 else METAL)
        p.drawEllipse(QRectF(x - 1, -28, 2, 2))
    for x in (-32, 32):
        p.setBrush(AMBER)
        p.drawEllipse(QRectF(x - 3.5, -21, 7, 7))
        p.setBrush(MINT)
        p.drawEllipse(QRectF(x - 2.5, -5, 5, 5))
        p.setBrush(METAL)
        p.drawEllipse(QRectF(x - 2.5, 9, 5, 5))
    for x, color in ((-13, AMBER), (0, MINT), (13, AMBER)):
        p.setBrush(color)
        p.drawEllipse(QRectF(x - 4, 21, 8, 8))
        p.setBrush(INK)
        p.drawEllipse(QRectF(x - 1.5, 23.5, 3, 3))


def _sport(p: QPainter) -> None:
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(INK, 14))
    p.drawEllipse(QRectF(-40, -40, 80, 80))
    p.setPen(QPen(RIM, 10))
    p.drawEllipse(QRectF(-40, -40, 80, 80))
    p.setPen(QPen(HIGHLIGHT, 1))
    p.drawArc(QRectF(-40, -40, 80, 80), 32 * 16, 106 * 16)
    p.setPen(Qt.NoPen)
    p.setBrush(METAL)
    for points in (
        ((-35, -6), (-8, -10), (-8, 3), (-35, 6)),
        ((35, -6), (8, -10), (8, 3), (35, 6)),
        ((-7, 5), (7, 5), (8, 35), (-8, 35)),
    ):
        p.drawPath(_polygon(points))
    p.setBrush(INK)
    p.drawEllipse(QRectF(-12, -12, 24, 24))
    p.setBrush(RIM)
    p.drawEllipse(QRectF(-9, -9, 18, 18))
    p.setPen(QPen(HIGHLIGHT, 1.5))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRectF(-4, -4, 8, 8))
    p.setPen(Qt.NoPen)
    p.setBrush(AMBER)
    p.drawRoundedRect(QRectF(-2.5, -44, 5, 9), 1.5, 1.5)


def _classic(p: QPainter) -> None:
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor("#583b32"), 14))
    p.drawEllipse(QRectF(-40, -40, 80, 80))
    p.setPen(QPen(QColor("#a97a52"), 9))
    p.drawEllipse(QRectF(-40, -40, 80, 80))
    p.setPen(QPen(AMBER, 1.2))
    p.drawArc(QRectF(-40, -40, 80, 80), 36 * 16, 105 * 16)
    p.setPen(Qt.NoPen)
    p.setBrush(METAL)
    for angle in (0, 90, 270):
        p.save()
        p.rotate(angle)
        p.drawPath(_polygon(((-7, -4), (7, -4), (5, 36), (-5, 36))))
        p.setBrush(QColor("#1a2936"))
        for y in (20, 29):
            p.drawEllipse(QRectF(-2, y - 2, 4, 4))
        p.setBrush(METAL)
        p.restore()
    p.setBrush(INK)
    p.drawEllipse(QRectF(-12, -12, 24, 24))
    p.setPen(QPen(HIGHLIGHT, 1.3))
    p.setBrush(QColor("#334454"))
    p.drawEllipse(QRectF(-8, -8, 16, 16))
    p.setPen(Qt.NoPen)
    p.setBrush(AMBER)
    p.drawEllipse(QRectF(-2, -2, 4, 4))
