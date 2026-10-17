from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF

from .config import Settings


HEIGHT = 164
FULL_WIDTH = 790
GAP = 20
DRIVE_WIDTH = 88
PEDALS_WIDTH = 82
RAIL_HEIGHT = 20


@dataclass(frozen=True)
class OverlayLayout:
    width: int
    height: int
    safe: QRectF
    wheel: QRectF | None
    drive: QRectF | None
    chart_column: QRectF
    chart: QRectF
    pedals: QRectF
    gas_track: QRectF
    brake_track: QRectF
    dividers: tuple[float, ...]
    wheel_size: float
    rail_y: float
    settings_button: QRectF
    close_button: QRectF


def build_layout(settings: Settings) -> OverlayLayout:
    """Place each visible section inside one symmetric, adjustable safe area."""
    inset = max(8, min(30, int(settings.safe_inset)))
    safe_height = HEIGHT - 2 * inset
    wheel_width = max(80, min(116, round(safe_height * .78)))
    chart_width = FULL_WIDTH - 2 * inset - wheel_width - DRIVE_WIDTH - PEDALS_WIDTH - 3 * GAP
    drive_width = (DRIVE_WIDTH if settings.show_gear and settings.show_speed else
                   76 if settings.show_gear or settings.show_speed else 0)

    sections: list[tuple[str, int]] = []
    if settings.show_steer:
        sections.append(("wheel", wheel_width))
    if drive_width:
        sections.append(("drive", drive_width))
    sections.extend((("chart", chart_width), ("pedals", PEDALS_WIDTH)))
    width = 2 * inset + sum(section_width for _, section_width in sections) + GAP * (len(sections) - 1)
    safe = QRectF(inset, inset, width - 2 * inset, safe_height)

    rects: dict[str, QRectF] = {}
    dividers: list[float] = []
    x = float(inset)
    for index, (name, section_width) in enumerate(sections):
        rects[name] = QRectF(x, inset, section_width, safe_height)
        x += section_width
        if index < len(sections) - 1:
            dividers.append(x + GAP / 2)
            x += GAP

    chart_column = rects["chart"]
    if settings.info_position == "top":
        chart = QRectF(chart_column.left(), safe.top() + RAIL_HEIGHT,
                       chart_column.width(), safe.height() - RAIL_HEIGHT)
        rail_y = safe.top() + 8
    else:
        chart = QRectF(chart_column.left(), safe.top(),
                       chart_column.width(), safe.height() - RAIL_HEIGHT)
        rail_y = safe.bottom() - 8

    pedals = rects["pedals"]
    gas_track = QRectF(pedals.left() + 2, safe.top(), 32, safe.height())
    brake_track = QRectF(pedals.right() - 34, safe.top(), 32, safe.height())
    return OverlayLayout(
        width=width, height=HEIGHT, safe=safe,
        wheel=rects.get("wheel"), drive=rects.get("drive"),
        chart_column=chart_column, chart=chart, pedals=pedals,
        gas_track=gas_track, brake_track=brake_track,
        dividers=tuple(dividers),
        wheel_size=min(wheel_width / .94, safe_height / .94)
        * (.94 if settings.wheel_style == "formula" else 1),
        rail_y=rail_y,
        settings_button=QRectF(chart_column.right() - 49, rail_y - 10, 21, 20),
        close_button=QRectF(chart_column.right() - 24, rail_y - 10, 21, 20),
    )
