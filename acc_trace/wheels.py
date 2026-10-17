from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPainterPathStroker, QPen, QTransform


# Shared palette and line weights keep all three wheels in the same family.
INK = QColor("#101923")
GRIP = QColor("#263747")
GRIP_LIGHT = QColor("#405364")
METAL = QColor("#718295")
SPORT_METAL = QColor("#465867")
HIGHLIGHT = QColor("#b6c5d3")
AMBER = QColor("#f0c84b")
MINT = QColor("#83dfb1")


def _polygon(points: tuple[tuple[float, float], ...]) -> QPainterPath:
    path = QPainterPath()
    path.moveTo(*points[0])
    for point in points[1:]:
        path.lineTo(*point)
    path.closeSubpath()
    return path


def _hole(path: QPainterPath, x: float, y: float, radius: float) -> QPainterPath:
    cutout = QPainterPath()
    cutout.addEllipse(QRectF(x - radius, y - radius, radius * 2, radius * 2))
    return path.subtracted(cutout)


def draw_wheel(p: QPainter, style: str, cx: float, cy: float, size: float, degrees: float) -> None:
    """Draw the three wheel designs on a shared 100-unit canvas."""
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
    # Wide upper bridge, rounded hand grips and a shallow lower bridge.
    outline = QPainterPath()
    outline.moveTo(0, -30)
    outline.cubicTo(17, -30, 33, -29, 41, -26)
    outline.cubicTo(47, -24, 49, -18, 49, -9)
    outline.cubicTo(50, 1, 49, 10, 47, 15)
    outline.cubicTo(46, 25, 41, 29, 34, 29)
    outline.cubicTo(29, 29, 26, 25, 23, 23)
    outline.cubicTo(15, 21, 9, 23, 0, 23)
    outline.cubicTo(-9, 23, -15, 21, -23, 23)
    outline.cubicTo(-26, 25, -29, 29, -34, 29)
    outline.cubicTo(-41, 29, -46, 25, -47, 15)
    outline.cubicTo(-49, 10, -50, 1, -49, -9)
    outline.cubicTo(-49, -18, -47, -24, -41, -26)
    outline.cubicTo(-33, -29, -17, -30, 0, -30)
    outline.closeSubpath()

    # Real transparent openings preserve the shape against any panel color.
    for side in (-1, 1):
        upper = QPainterPath()
        upper.moveTo(side * 27, -18)
        upper.cubicTo(side * 32, -19, side * 38, -18, side * 40, -15)
        upper.cubicTo(side * 42, -12, side * 41, -7, side * 39, -5)
        upper.cubicTo(side * 36, -3, side * 31, -5, side * 27, -5)
        upper.cubicTo(side * 25, -8, side * 25, -15, side * 27, -18)
        upper.closeSubpath()
        lower = QPainterPath()
        lower.moveTo(side * 28, 7)
        lower.cubicTo(side * 34, 4, side * 41, 6, side * 41, 12)
        lower.cubicTo(side * 41, 19, side * 37, 23, side * 33, 23)
        lower.cubicTo(side * 27, 23, side * 24, 13, side * 28, 7)
        lower.closeSubpath()
        outline = outline.subtracted(upper).subtracted(lower)

    p.setPen(QPen(GRIP_LIGHT, 1.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(INK)
    p.drawPath(outline)
    p.setPen(QPen(GRIP, 3.3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    for side in (-1, 1):
        grip_line = QPainterPath()
        grip_line.moveTo(side * 44, -11)
        grip_line.cubicTo(side * 45, -4, side * 45.5, 5, side * 44, 12)
        grip_line.cubicTo(side * 43.7, 13.5, side * 43.4, 14.5,
                          side * 43, 15.5)
        p.drawPath(grip_line)
    p.setPen(QPen(GRIP_LIGHT, 1.2, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(-17, -27, 17, -27)

    plate = QPainterPath()
    plate.moveTo(-21, -20.5)
    plate.lineTo(21, -20.5)
    plate.cubicTo(25, -16, 25, 8, 19, 17)
    plate.cubicTo(12, 21, -12, 21, -19, 17)
    plate.cubicTo(-25, 8, -25, -16, -21, -20.5)
    plate.closeSubpath()
    p.setPen(QPen(GRIP_LIGHT, .9))
    p.setBrush(QColor("#1c2b39"))
    p.drawPath(plate)

    # All controls sit inside the plate, spaced around the larger readout.
    p.setPen(QPen(METAL, .8))
    p.setBrush(INK)
    p.drawRoundedRect(QRectF(-14.5, -18, 29, 12.5), 1.5, 1.5)
    p.setPen(QPen(MINT, 1.2, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(-9, -11.5, 1, -11.5)
    p.drawLine(5, -11.5, 10, -11.5)
    p.setPen(Qt.NoPen)
    for x in (-12, -6, 0, 6, 12):
        p.setBrush(MINT if abs(x) <= 6 else AMBER)
        p.drawRoundedRect(QRectF(x - 1.5, -25, 3, 2), .6, .6)
    for side in (-1, 1):
        p.setBrush(METAL)
        p.drawEllipse(QRectF(side * 19.5 - 2.2, -14.8, 4.4, 4.4))
        p.setBrush(GRIP)
        p.drawEllipse(QRectF(side * 12 - 4.6, .4, 9.2, 9.2))
        p.setBrush(AMBER)
        p.drawEllipse(QRectF(side * 12 - 3.1, 1.9, 6.2, 6.2))
        p.setBrush(HIGHLIGHT)
        p.drawEllipse(QRectF(side * 9 - 2.4, 11.2, 4.8, 4.8))
    p.setBrush(GRIP)
    p.drawEllipse(QRectF(-4.6, .4, 9.2, 9.2))
    p.setBrush(MINT)
    p.drawEllipse(QRectF(-3.1, 1.9, 6.2, 6.2))
    p.setBrush(METAL)
    p.drawEllipse(QRectF(-2.4, 11.2, 4.8, 4.8))


def _classic_rim(p: QPainter) -> None:
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor("#4a3433"), 11, Qt.SolidLine, Qt.RoundCap))
    p.drawEllipse(QRectF(-42, -42, 84, 84))
    p.setPen(QPen(QColor("#815e50"), 7.5, Qt.SolidLine, Qt.RoundCap))
    p.drawEllipse(QRectF(-42, -42, 84, 84))
    p.setPen(QPen(QColor("#ae8470"), 1.1))
    p.drawArc(QRectF(-42, -42, 84, 84), 32 * 16, 116 * 16)
    p.setPen(QPen(AMBER, 4.6, Qt.SolidLine, Qt.FlatCap))
    p.drawLine(0, -47.2, 0, -37)


def _sport_rim_path() -> QPainterPath:
    # Match the classic rim's 11-unit band centered on a 42-unit radius.
    outer = QPainterPath()
    outer.addEllipse(QRectF(-47.5, -47.5, 95, 95))
    inner = QPainterPath()
    inner.addEllipse(QRectF(-36.5, -36.5, 73, 73))
    rim = outer.subtracted(inner)

    # The leather wraps over all three spoke ends. Joining it to the ring
    # before outlining gives both edges one continuous contour.
    collar = QPainterPath()
    collar.moveTo(-4.5, 32)
    collar.cubicTo(-7, 33, -8, 37, -7, 41)
    collar.lineTo(7, 41)
    collar.cubicTo(8, 37, 7, 33, 4.5, 32)
    collar.closeSubpath()
    for angle in (0, 90, -90):
        rim = rim.united(QTransform().rotate(angle).map(collar))
    return rim


def _draw_sport_rim(p: QPainter) -> None:
    rim = _sport_rim_path()
    edge = QPainterPathStroker()
    edge.setWidth(3.5)  # Leaves the same 7.5-unit face as the classic rim.
    edge.setJoinStyle(Qt.RoundJoin)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#3b4d5b"))
    p.drawPath(rim)
    p.setBrush(GRIP)
    p.drawPath(rim.subtracted(edge.createStroke(rim)))
    p.setPen(QPen(AMBER, 4.6, Qt.SolidLine, Qt.FlatCap))
    p.drawLine(0, -47.2, 0, -37)


def _sport(p: QPainter) -> None:
    # One tapered spoke is rotated three times, so its width and holes match.
    spoke = _polygon(((-7.3, 8), (7.3, 8), (5.5, 17),
                      (3.8, 38), (-3.8, 38), (-5.5, 17)))
    for y, radius in ((20, 2.6), (29, 2.1)):
        spoke = _hole(spoke, 0, y, radius)
    p.setPen(QPen(METAL, .8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(SPORT_METAL)
    for angle in (0, 90, -90):
        p.save()
        p.rotate(angle)
        p.drawPath(spoke)
        p.restore()

    _draw_sport_rim(p)

    p.setPen(QPen(GRIP_LIGHT, 1.2))
    p.setBrush(INK)
    p.drawEllipse(QRectF(-12, -12, 24, 24))
    p.setPen(QPen(METAL, 1.2))
    p.setBrush(GRIP)
    p.drawEllipse(QRectF(-8.5, -8.5, 17, 17))
    p.setPen(QPen(AMBER, 1.3))
    p.setBrush(INK)
    p.drawEllipse(QRectF(-4.5, -4.5, 9, 9))


def _classic(p: QPainter) -> None:
    _classic_rim(p)
    p.setPen(QPen(HIGHLIGHT, .8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(METAL)
    for side in (-1, 1):
        spoke = _polygon(((side * 7, -7), (side * 14, -9),
                          (side * 38, -7), (side * 38, 1),
                          (side * 14, 5), (side * 7, 8)))
        slot = _polygon(((side * 17, -3.8), (side * 34, -3),
                         (side * 34, -1), (side * 17, 1)))
        p.drawPath(spoke.subtracted(slot))
    lower = _polygon(((-7, 5), (7, 5), (4.5, 37), (-4.5, 37)))
    slot = _polygon(((-1.3, 17), (1.3, 17), (1, 32), (-1, 32)))
    p.drawPath(lower.subtracted(slot))

    p.setPen(QPen(HIGHLIGHT, 1.1))
    p.setBrush(METAL)
    p.drawEllipse(QRectF(-12, -12, 24, 24))
    p.setPen(QPen(INK, 1))
    p.setBrush(GRIP)
    p.drawEllipse(QRectF(-9, -9, 18, 18))
    p.setPen(QPen(METAL, .8))
    p.setBrush(INK)
    p.drawEllipse(QRectF(-5.5, -5.5, 11, 11))
