from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path


def settings_path() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home() / ".config")
    return base / "ACC Trace" / "settings.json"


@dataclass
class Settings:
    # The render timer uses the same rate as the telemetry polling timer.
    update_hz: int = 60
    graph_speed: int = 95  # screen pixels per second
    avoid_trace_overlap: bool = False
    smoothing_ms: int = 65
    opacity: int = 94  # percent, applied to the whole overlay
    source: str = "acc"  # acc, controller, demo
    controller_guid: str = ""
    gas_axis: int = 2
    brake_axis: int = 3
    steer_axis: int = 0
    invert_gas: bool = False
    invert_brake: bool = False
    invert_steer: bool = False
    show_steer: bool = True
    wheel_style: str = "formula"  # formula, sport, classic
    info_position: str = "top"  # top, bottom
    language: str = "ru"  # ru, en
    steering_lock_deg: int = 540  # total lock-to-lock rotation of the wheel icon
    show_speed: bool = True
    show_gear: bool = True
    x: int | None = None
    y: int | None = None

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        path = path or settings_path()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            known = {field.name for field in fields(cls)}
            values = {key: value for key, value in raw.items() if key in known}
            result = cls(**values)
            result.validate()
            return result
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self, path: Path | None = None) -> None:
        self.validate()
        path = path or settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    def validate(self) -> None:
        if self.update_hz not in (30, 60, 90, 120):
            self.update_hz = 60
        self.graph_speed = max(30, min(180, int(self.graph_speed)))
        self.smoothing_ms = max(0, min(200, int(self.smoothing_ms)))
        self.opacity = max(35, min(100, int(self.opacity)))
        self.steering_lock_deg = max(180, min(1080, int(self.steering_lock_deg)))
        if self.source not in ("acc", "controller", "demo"):
            self.source = "acc"
        if self.wheel_style not in ("formula", "sport", "classic"):
            self.wheel_style = "formula"
        if self.info_position not in ("top", "bottom"):
            self.info_position = "top"
        if self.language not in ("ru", "en"):
            self.language = "ru"
        for name in ("gas_axis", "brake_axis", "steer_axis"):
            setattr(self, name, max(0, min(31, int(getattr(self, name)))))

