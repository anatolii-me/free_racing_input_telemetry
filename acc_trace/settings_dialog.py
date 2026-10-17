from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget,
)

from .config import Settings
from .controller import AXIS_NAMES, ControllerReader


STYLE = """
QDialog { background: #121c28; color: #f3f6fb; font-family: 'Segoe UI Variable', 'Segoe UI'; }
QLabel { color: #dce5ef; font-size: 12px; }
QLabel#subtitle, QLabel#hint { color: #8e9dad; }
QLabel#section { color: #9aabba; font-weight: 600; font-size: 11px; }
QFrame#card { background: #1b2938; border: 1px solid #304152; border-radius: 13px; }
QComboBox { background: #273747; border: 1px solid #405267; border-radius: 8px; padding: 6px 10px; min-height: 19px; color: #f3f6fb; }
QComboBox QAbstractItemView { background: #233243; color: #f3f6fb; selection-background-color: #3a5265; }
QPushButton { background: #293b4c; border: 1px solid #405267; border-radius: 8px; padding: 8px 14px; color: #edf3f9; }
QPushButton:hover { background: #34495b; }
QPushButton#primary { background: #83dfb1; border-color: #83dfb1; color: #102018; font-weight: 600; }
QPushButton#primary:hover { background: #a0edc7; }
QCheckBox { color: #dce5ef; spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; }
QSlider::groove:horizontal { height: 5px; border-radius: 2px; background: #34495b; }
QSlider::sub-page:horizontal { background: #83dfb1; border-radius: 2px; }
QSlider::handle:horizontal { background: #edf9f2; width: 15px; margin: -5px 0; border-radius: 7px; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { width: 8px; background: transparent; }
QScrollBar::handle:vertical { background: #41576a; border-radius: 4px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, controller: ControllerReader, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки · ACC Trace")
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setModal(False)
        self.setMinimumWidth(540)
        self.setStyleSheet(STYLE)
        self.controller = controller
        self._devices_scanned = False
        self._pending_guid = settings.controller_guid
        self.result_settings = settings

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(15)
        title = QLabel("Настройки")
        title.setStyleSheet("font-size: 23px; font-weight: 600; color: #f6f9fc;")
        root.addWidget(title)
        subtitle = QLabel("Настройте поведение оверлея под свой риг и монитор.")
        subtitle.setObjectName("subtitle")
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 3, 0, 3)
        body.setSpacing(15)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)
        self._scroll = scroll
        self._content = content

        display_card, display_layout = self._card("ОТОБРАЖЕНИЕ")
        self.speed_slider, self.speed_value = self._slider(display_layout, "Скорость графика", 30, 180, "px/s")
        self.smooth_slider, self.smooth_value = self._slider(display_layout, "Сглаживание", 0, 200, "мс")
        self.opacity_slider, self.opacity_value = self._slider(display_layout, "Непрозрачность", 35, 100, "%")
        self.steering_slider, self.steering_value = self._slider(display_layout, "Поворот руля от упора до упора", 180, 1080, "°")
        rate_row = QHBoxLayout()
        rate_row.addWidget(QLabel("Обновление / FPS"))
        rate_row.addStretch()
        self.rate_combo = QComboBox()
        for rate in (30, 60, 90, 120):
            self.rate_combo.addItem(f"{rate} Гц · до {rate} FPS", rate)
        rate_row.addWidget(self.rate_combo)
        display_layout.addLayout(rate_row)
        body.addWidget(display_card)

        source_card, source_layout = self._card("ИСТОЧНИК И ОСИ")
        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Источник педалей и руля"))
        source_row.addStretch()
        self.source_combo = QComboBox()
        self.source_combo.addItem("Телеметрия ACC", "acc")
        self.source_combo.addItem("Руль / геймпад", "controller")
        self.source_combo.addItem("Демо", "demo")
        source_row.addWidget(self.source_combo)
        source_layout.addLayout(source_row)
        self.source_hint = QLabel("ACC считывает игровые значения; оси ниже нужны для прямого чтения контроллера.")
        self.source_hint.setObjectName("hint")
        self.source_hint.setWordWrap(True)
        source_layout.addWidget(self.source_hint)
        self.axes_panel = QWidget()
        axes_layout = QGridLayout(self.axes_panel)
        axes_layout.setContentsMargins(0, 5, 0, 0)
        axes_layout.setHorizontalSpacing(10)
        axes_layout.setVerticalSpacing(9)
        axes_layout.addWidget(QLabel("Устройство"), 0, 0)
        self.device_combo = QComboBox()
        axes_layout.addWidget(self.device_combo, 0, 1)
        refresh = QPushButton("Обновить")
        refresh.clicked.connect(lambda: self._refresh_devices())
        axes_layout.addWidget(refresh, 0, 2)
        self.axes: dict[str, QComboBox] = {}
        self.inverts: dict[str, QCheckBox] = {}
        for row, (name, label) in enumerate((("gas", "Газ"), ("brake", "Тормоз"), ("steer", "Руль")), start=1):
            axes_layout.addWidget(QLabel(label), row, 0)
            combo = QComboBox()
            for axis, axis_name in enumerate(AXIS_NAMES):
                combo.addItem(f"{axis_name} · ось {axis}", axis)
            axes_layout.addWidget(combo, row, 1)
            self.axes[name] = combo
            invert = QCheckBox("Инверсия")
            axes_layout.addWidget(invert, row, 2)
            self.inverts[name] = invert
        source_layout.addWidget(self.axes_panel)
        body.addWidget(source_card)

        visibility_card, visibility_layout = self._card("ПОКАЗЫВАТЬ")
        checks = QHBoxLayout()
        self.show_steer = QCheckBox("Руль")
        self.show_speed = QCheckBox("Скорость")
        self.show_gear = QCheckBox("Передача")
        for check in (self.show_steer, self.show_speed, self.show_gear):
            checks.addWidget(check)
        checks.addStretch()
        visibility_layout.addLayout(checks)
        body.addWidget(visibility_card)

        footer = QHBoxLayout()
        reset = QPushButton("По умолчанию")
        reset.clicked.connect(self._restore_defaults)
        footer.addWidget(reset)
        footer.addStretch()
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        save = QPushButton("Сохранить")
        save.setObjectName("primary")
        save.clicked.connect(self._accept)
        footer.addWidget(save)
        root.addLayout(footer)

        self.source_combo.currentIndexChanged.connect(self._update_source)
        self._load(settings)
        self.adjustSize()
        self._fit_height()

    def _card(self, heading: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(17, 14, 17, 16)
        layout.setSpacing(12)
        title = QLabel(heading)
        title.setObjectName("section")
        layout.addWidget(title)
        return card, layout

    def _slider(self, layout: QVBoxLayout, title: str, low: int, high: int, suffix: str) -> tuple[QSlider, QLabel]:
        row = QHBoxLayout()
        row.addWidget(QLabel(title))
        row.addStretch()
        value = QLabel()
        value.setMinimumWidth(66)
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(value)
        layout.addLayout(row)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(low, high)
        slider.valueChanged.connect(lambda number: value.setText(f"{number} {suffix}"))
        layout.addWidget(slider)
        return slider, value

    def _refresh_devices(self, selected_guid: str | None = None) -> None:
        selected_guid = self.device_combo.currentData() if selected_guid is None else selected_guid
        self.device_combo.clear()
        try:
            devices = self.controller.devices()
        except Exception:
            devices = []
        if not devices:
            self.device_combo.addItem("Устройство не найдено", "")
        else:
            for guid, name in devices:
                self.device_combo.addItem(name, guid)
        if selected_guid and selected_guid.isdecimal() and self.device_combo.findData(selected_guid) < 0:
            self.device_combo.addItem("Ранее выбранное устройство (отключено)", selected_guid)
        index = self.device_combo.findData(selected_guid)
        self.device_combo.setCurrentIndex(max(0, index))
        self._devices_scanned = True

    def _load(self, settings: Settings) -> None:
        self._pending_guid = settings.controller_guid
        self._devices_scanned = False
        self.speed_slider.setValue(settings.graph_speed)
        self.smooth_slider.setValue(settings.smoothing_ms)
        self.opacity_slider.setValue(settings.opacity)
        self.steering_slider.setValue(settings.steering_lock_deg)
        self.rate_combo.setCurrentIndex(self.rate_combo.findData(settings.update_hz))
        self.source_combo.blockSignals(True)
        self.source_combo.setCurrentIndex(self.source_combo.findData(settings.source))
        self.source_combo.blockSignals(False)
        self.device_combo.clear()
        self.device_combo.addItem("Выберите режим руля для поиска устройства", settings.controller_guid)
        for name in ("gas", "brake", "steer"):
            combo = self.axes[name]
            while combo.count() > len(AXIS_NAMES):
                combo.removeItem(len(AXIS_NAMES))
            index = getattr(settings, f"{name}_axis")
            if combo.findData(index) < 0:
                combo.addItem(f"Ось {index} недоступна в WinMM", index)
            combo.setCurrentIndex(combo.findData(index))
            self.inverts[name].setChecked(getattr(settings, f"invert_{name}"))
        self.show_steer.setChecked(settings.show_steer)
        self.show_speed.setChecked(settings.show_speed)
        self.show_gear.setChecked(settings.show_gear)
        self._update_source()

    def _restore_defaults(self) -> None:
        self._load(Settings(x=self.result_settings.x, y=self.result_settings.y))

    def _update_source(self) -> None:
        controller = self.source_combo.currentData() == "controller"
        if controller and not self._devices_scanned:
            self._refresh_devices(self._pending_guid)
        self.axes_panel.setVisible(controller)
        self.source_hint.setVisible(not controller)
        self._fit_height()

    def _fit_height(self) -> None:
        self._content.layout().activate()
        natural = self.layout().sizeHint().height() - self._scroll.sizeHint().height() + self._content.sizeHint().height() + 10
        screen = QGuiApplication.primaryScreen()
        ceiling = max(500, screen.availableGeometry().height() - 50) if screen is not None else natural
        self.setMaximumHeight(ceiling)
        self.resize(max(540, self.width()), min(natural, ceiling))

    def _accept(self) -> None:
        self.result_settings = replace(
            self.result_settings,
            graph_speed=self.speed_slider.value(),
            smoothing_ms=self.smooth_slider.value(),
            opacity=self.opacity_slider.value(),
            steering_lock_deg=self.steering_slider.value(),
            update_hz=self.rate_combo.currentData(),
            source=self.source_combo.currentData(),
            controller_guid=self.device_combo.currentData() or "",
            gas_axis=self.axes["gas"].currentData(),
            brake_axis=self.axes["brake"].currentData(),
            steer_axis=self.axes["steer"].currentData(),
            invert_gas=self.inverts["gas"].isChecked(),
            invert_brake=self.inverts["brake"].isChecked(),
            invert_steer=self.inverts["steer"].isChecked(),
            show_steer=self.show_steer.isChecked(),
            show_speed=self.show_speed.isChecked(),
            show_gear=self.show_gear.isChecked(),
        )
        self.accept()
