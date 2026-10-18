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
    chart_column: QRectF | None
    chart: QRectF | None
    pedals: QRectF | None
    gas_track: QRectF | None
    brake_track: QRectF | None
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
    if settings.show_history:
        sections.append(("chart", chart_width))
    pedal_width = PEDALS_WIDTH if settings.show_gas and settings.show_brake else 36
    if settings.show_gas or settings.show_brake:
        sections.append(("pedals", pedal_width))
    content_width = sum(section_width for _, section_width in sections) + GAP * max(0, len(sections) - 1)
    safe_width = max(96, content_width)
    width = 2 * inset + safe_width
    safe = QRectF(inset, inset, safe_width, safe_height)

    rects: dict[str, QRectF] = {}
    dividers: list[float] = []
    x = float(inset + (safe_width - content_width) / 2)
    for index, (name, section_width) in enumerate(sections):
        rects[name] = QRectF(x, inset, section_width, safe_height)
        x += section_width
        if index < len(sections) - 1:
            dividers.append(x + GAP / 2)
            x += GAP

    chart_column = rects.get("chart")
    if not settings.show_info_bar:
        chart = QRectF(chart_column) if chart_column is not None else None
        rail_y = safe.top() + 12 if settings.info_position == "top" else safe.bottom() - 12
    elif settings.info_position == "top":
        chart = (QRectF(chart_column.left(), safe.top() + RAIL_HEIGHT,
                        chart_column.width(), safe.height() - RAIL_HEIGHT)
                 if chart_column is not None else None)
        rail_y = safe.top() + 8
    else:
        chart = (QRectF(chart_column.left(), safe.top(),
                        chart_column.width(), safe.height() - RAIL_HEIGHT)
                 if chart_column is not None else None)
        rail_y = safe.bottom() - 8

    pedals = rects.get("pedals")
    gas_track = None
    brake_track = None
    if pedals is not None:
        if settings.show_gas:
            gas_track = QRectF(pedals.left() + 2, safe.top(), 32, safe.height())
        if settings.show_brake:
            brake_track = QRectF(pedals.right() - 34, safe.top(), 32, safe.height())
    controls_right = chart_column.right() if chart_column is not None else safe.right()
    return OverlayLayout(
        width=width, height=HEIGHT, safe=safe,
        wheel=rects.get("wheel"), drive=rects.get("drive"),
        chart_column=chart_column, chart=chart, pedals=pedals,
        gas_track=gas_track, brake_track=brake_track,
        dividers=tuple(dividers),
        wheel_size=min(wheel_width / .94, safe_height / .94)
        * (.94 if settings.wheel_style == "formula" else 1),
        rail_y=rail_y,
        settings_button=QRectF(controls_right - 49, rail_y - 10, 21, 20),
        close_button=QRectF(controls_right - 24, rail_y - 10, 21, 20),
    )
