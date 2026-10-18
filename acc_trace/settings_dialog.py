from __future__ import annotations

from dataclasses import replace
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from .config import Settings
from .controller import AXIS_NAMES, AxisDetector, ControllerReader
from .i18n import tr


STYLE = """
QDialog { background: #121c28; color: #f3f6fb; font-family: 'Segoe UI Variable', 'Segoe UI'; }
QLabel { color: #dce5ef; font-size: 12px; }
QLabel#subtitle, QLabel#hint { color: #8e9dad; }
QLabel#section { color: #9aabba; font-weight: 600; font-size: 11px; }
QFrame#card { background: #1b2938; border: 1px solid #304152; border-radius: 13px; }
QComboBox { background: #273747; border: 1px solid #405267; border-radius: 8px; padding: 6px 10px; min-height: 19px; color: #f3f6fb; }
QComboBox QAbstractItemView { background: #233243; color: #f3f6fb; selection-background-color: #3a5265; }
QSpinBox { background: #273747; border: 1px solid #405267; border-radius: 8px; padding: 6px 10px; min-height: 19px; color: #f3f6fb; }
QPushButton { background: #293b4c; border: 1px solid #405267; border-radius: 8px; padding: 8px 14px; color: #edf3f9; }
QPushButton:hover { background: #34495b; }
QPushButton#primary { background: #83dfb1; border-color: #83dfb1; color: #102018; font-weight: 600; }
QPushButton#primary:hover { background: #a0edc7; }
QCheckBox { color: #dce5ef; spacing: 8px; }
QCheckBox::indicator { width: 14px; height: 14px; background: #172534; border: 1px solid #53677a; border-radius: 3px; }
QCheckBox::indicator:checked { background: #83dfb1; border-color: #83dfb1; }
QSlider::groove:horizontal { height: 5px; border-radius: 2px; background: #34495b; }
QSlider::sub-page:horizontal { background: #83dfb1; border-radius: 2px; }
QSlider::handle:horizontal { background: #edf9f2; width: 15px; margin: -5px 0; border-radius: 7px; }
QScrollArea { background: transparent; border: none; }
QWidget#scrollContent { background: #121c28; }
QScrollBar:vertical { width: 8px; background: transparent; }
QScrollBar::handle:vertical { background: #41576a; border-radius: 4px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, controller: ControllerReader, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.language = settings.language
        self.setWindowTitle(self._t("settings_title"))
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setModal(False)
        self.setMinimumWidth(540)
        self.setStyleSheet(STYLE)
        self.controller = controller
        self._devices_scanned = False
        self._pending_guid = settings.controller_guid
        self.result_settings = settings
        self._axis_detector: AxisDetector | None = None
        self._learning_axis: str | None = None
        self._learn_started = 0.0
        self._learn_timer = QTimer(self)
        self._learn_timer.setInterval(40)
        self._learn_timer.timeout.connect(self._poll_axis)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(15)
        title = QLabel(self._t("settings"))
        title.setStyleSheet("font-size: 23px; font-weight: 600; color: #f6f9fc;")
        root.addWidget(title)
        subtitle = QLabel(self._t("subtitle"))
        subtitle.setObjectName("subtitle")
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("scrollContent")
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 3, 0, 3)
        body.setSpacing(15)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)
        self._scroll = scroll
        self._content = content

        appearance_card, appearance_layout = self._card(self._t("appearance"))
        self.wheel_combo = QComboBox()
        for style in ("formula", "sport", "classic"):
            self.wheel_combo.addItem(self._t(style), style)
        self._choice_row(appearance_layout, self._t("wheel_style"), self.wheel_combo)
        self.info_combo = QComboBox()
        for position in ("top", "bottom"):
            self.info_combo.addItem(self._t(position), position)
        self._choice_row(appearance_layout, self._t("info_position"), self.info_combo)
        self.show_info_bar = QCheckBox(self._t("show_info_bar"))
        appearance_layout.addWidget(self.show_info_bar)
        self.safe_slider, self.safe_value = self._slider(
            appearance_layout, self._t("safe_inset"), 8, 30, "px")
        self.language_combo = QComboBox()
        self.language_combo.addItem("Русский", "ru")
        self.language_combo.addItem("English", "en")
        self._choice_row(appearance_layout, self._t("language"), self.language_combo)
        body.addWidget(appearance_card)

        display_card, display_layout = self._card(self._t("display"))
        self.speed_slider, self.speed_value = self._slider(display_layout, self._t("graph_speed"), 30, 180, "px/s")
        self.avoid_trace_overlap = QCheckBox(self._t("avoid_trace_overlap"))
        display_layout.addWidget(self.avoid_trace_overlap)
        self.smooth_slider, self.smooth_value = self._slider(display_layout, self._t("smoothing"), 0, 200, self._t("milliseconds"))
        self.opacity_slider, self.opacity_value = self._slider(display_layout, self._t("opacity"), 35, 100, "%")
        self.steering_slider, self.steering_value = self._slider(display_layout, self._t("steering_lock"), 180, 1080, "°")
        rate_row = QHBoxLayout()
        rate_row.addWidget(QLabel(self._t("update_rate")))
        rate_row.addStretch()
        self.rate_combo = QComboBox()
        for rate in (30, 60, 90, 120):
            self.rate_combo.addItem(self._t("rate_item", rate=rate), rate)
        rate_row.addWidget(self.rate_combo)
        display_layout.addLayout(rate_row)
        body.addWidget(display_card)

        source_card, source_layout = self._card(self._t("source_section"))
        source_row = QHBoxLayout()
        source_row.addWidget(QLabel(self._t("source")))
        source_row.addStretch()
        self.source_combo = QComboBox()
        for source in ("game", "controller", "demo"):
            self.source_combo.addItem(self._t(source), source)
        source_row.addWidget(self.source_combo)
        source_layout.addLayout(source_row)
        self.source_hint = QLabel(self._t("source_hint_game"))
        self.source_hint.setObjectName("hint")
        self.source_hint.setWordWrap(True)
        source_layout.addWidget(self.source_hint)
        self.forza_port_row = QWidget()
        forza_port_layout = QHBoxLayout(self.forza_port_row)
        forza_port_layout.setContentsMargins(0, 0, 0, 0)
        forza_port_layout.addWidget(QLabel(self._t("forza_port")))
        forza_port_layout.addStretch()
        self.forza_port = QSpinBox()
        self.forza_port.setRange(1024, 65535)
        forza_port_layout.addWidget(self.forza_port)
        source_layout.addWidget(self.forza_port_row)
        self.f1_port_row = QWidget()
        f1_port_layout = QHBoxLayout(self.f1_port_row)
        f1_port_layout.setContentsMargins(0, 0, 0, 0)
        f1_port_layout.addWidget(QLabel(self._t("f1_port")))
        f1_port_layout.addStretch()
        self.f1_port = QSpinBox()
        self.f1_port.setRange(1024, 65535)
        f1_port_layout.addWidget(self.f1_port)
        source_layout.addWidget(self.f1_port_row)
        self.axes_panel = QWidget()
        axes_layout = QGridLayout(self.axes_panel)
        axes_layout.setContentsMargins(0, 5, 0, 0)
        axes_layout.setHorizontalSpacing(10)
        axes_layout.setVerticalSpacing(9)
        axes_layout.addWidget(QLabel(self._t("device")), 0, 0)
        self.device_combo = QComboBox()
        axes_layout.addWidget(self.device_combo, 0, 1)
        refresh = QPushButton(self._t("refresh"))
        refresh.clicked.connect(lambda: self._refresh_devices())
        axes_layout.addWidget(refresh, 0, 2)
        self.axes: dict[str, QComboBox] = {}
        self.inverts: dict[str, QCheckBox] = {}
        self.learn_buttons: dict[str, QPushButton] = {}
        for row, name in enumerate(("gas", "brake", "steer"), start=1):
            axes_layout.addWidget(QLabel(self._t(name)), row, 0)
            combo = QComboBox()
            for axis, axis_name in enumerate(AXIS_NAMES):
                combo.addItem(self._t("axis_number", name=axis_name, index=axis), axis)
            axes_layout.addWidget(combo, row, 1)
            self.axes[name] = combo
            learn = QPushButton(self._t("detect_axis"))
            learn.clicked.connect(lambda _checked=False, axis=name: self._start_axis_learning(axis))
            axes_layout.addWidget(learn, row, 2)
            self.learn_buttons[name] = learn
            invert = QCheckBox(self._t("invert"))
            axes_layout.addWidget(invert, row, 3)
            self.inverts[name] = invert
        self.learn_hint = QLabel(self._t("detect_hint"))
        self.learn_hint.setObjectName("hint")
        self.learn_hint.setWordWrap(True)
        axes_layout.addWidget(self.learn_hint, 4, 0, 1, 4)
        self.device_combo.currentIndexChanged.connect(self._stop_axis_learning)
        source_layout.addWidget(self.axes_panel)
        body.addWidget(source_card)

        visibility_card, visibility_layout = self._card(self._t("visibility"))
        checks = QHBoxLayout()
        self.show_steer = QCheckBox(self._t("steer"))
        self.show_speed = QCheckBox(self._t("speed"))
        self.show_gear = QCheckBox(self._t("gear"))
        for check in (self.show_steer, self.show_speed, self.show_gear):
            checks.addWidget(check)
        checks.addStretch()
        visibility_layout.addLayout(checks)
        self.show_pedal_values = QCheckBox(self._t("pedal_values"))
        visibility_layout.addWidget(self.show_pedal_values)
        block_checks = QHBoxLayout()
        self.show_history = QCheckBox(self._t("show_history"))
        self.show_gas = QCheckBox(self._t("show_gas"))
        self.show_brake = QCheckBox(self._t("show_brake"))
        for check in (self.show_history, self.show_gas, self.show_brake):
            block_checks.addWidget(check)
        block_checks.addStretch()
        visibility_layout.addLayout(block_checks)
        body.addWidget(visibility_card)

        footer = QHBoxLayout()
        reset = QPushButton(self._t("defaults"))
        reset.clicked.connect(self._restore_defaults)
        footer.addWidget(reset)
        footer.addStretch()
        cancel = QPushButton(self._t("cancel"))
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        save = QPushButton(self._t("save"))
        save.setObjectName("primary")
        save.clicked.connect(self._accept)
        footer.addWidget(save)
        root.addLayout(footer)

        self.source_combo.currentIndexChanged.connect(self._update_source)
        self._load(settings)
        self.adjustSize()
        self._fit_height()

    def _t(self, key: str, **values: object) -> str:
        return tr(self.language, key, **values)

    def _choice_row(self, layout: QVBoxLayout, title: str, combo: QComboBox) -> None:
        row = QHBoxLayout()
        row.addWidget(QLabel(title))
        row.addStretch()
        combo.setMinimumWidth(175)
        row.addWidget(combo)
        layout.addLayout(row)

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
        self.device_combo.addItem(self._t("auto_device"), "")
        try:
            devices = self.controller.devices()
        except Exception:
            devices = []
        if not devices:
            self.learn_hint.setText(self._t("no_device"))
        else:
            for guid, name in devices:
                self.device_combo.addItem(name, guid)
        if selected_guid and selected_guid.isdecimal() and self.device_combo.findData(selected_guid) < 0:
            self.device_combo.addItem(self._t("old_device"), selected_guid)
        index = self.device_combo.findData(selected_guid)
        self.device_combo.setCurrentIndex(max(0, index))
        self._devices_scanned = True

    def _load(self, settings: Settings) -> None:
        self._pending_guid = settings.controller_guid
        self._devices_scanned = False
        self.wheel_combo.setCurrentIndex(self.wheel_combo.findData(settings.wheel_style))
        self.info_combo.setCurrentIndex(self.info_combo.findData(settings.info_position))
        self.show_info_bar.setChecked(settings.show_info_bar)
        self.safe_slider.setValue(settings.safe_inset)
        self.language_combo.setCurrentIndex(self.language_combo.findData(settings.language))
        self.speed_slider.setValue(settings.graph_speed)
        self.avoid_trace_overlap.setChecked(settings.avoid_trace_overlap)
        self.smooth_slider.setValue(settings.smoothing_ms)
        self.opacity_slider.setValue(settings.opacity)
        self.steering_slider.setValue(settings.steering_lock_deg)
        self.rate_combo.setCurrentIndex(self.rate_combo.findData(settings.update_hz))
        self.forza_port.setValue(settings.forza_port)
        self.f1_port.setValue(settings.f1_port)
        self.source_combo.blockSignals(True)
        source = settings.source if settings.source in ("game", "controller", "demo") else "game"
        self.source_combo.setCurrentIndex(self.source_combo.findData(source))
        self.source_combo.blockSignals(False)
        self.device_combo.clear()
        self.device_combo.addItem(self._t("auto_device"), settings.controller_guid)
        for name in ("gas", "brake", "steer"):
            combo = self.axes[name]
            while combo.count() > len(AXIS_NAMES):
                combo.removeItem(len(AXIS_NAMES))
            index = getattr(settings, f"{name}_axis")
            if combo.findData(index) < 0:
                combo.addItem(self._t("axis_unavailable", index=index), index)
            combo.setCurrentIndex(combo.findData(index))
            self.inverts[name].setChecked(getattr(settings, f"invert_{name}"))
        self.show_steer.setChecked(settings.show_steer)
        self.show_speed.setChecked(settings.show_speed)
        self.show_gear.setChecked(settings.show_gear)
        self.show_pedal_values.setChecked(settings.show_pedal_values)
        self.show_history.setChecked(settings.show_history)
        self.show_gas.setChecked(settings.show_gas)
        self.show_brake.setChecked(settings.show_brake)
        self._update_source()

    def _restore_defaults(self) -> None:
        self._stop_axis_learning()
        self._load(Settings(x=self.result_settings.x, y=self.result_settings.y))

    def _update_source(self) -> None:
        source = self.source_combo.currentData()
        controller = source == "controller"
        if not controller:
            self._stop_axis_learning()
        if controller and not self._devices_scanned:
            self._refresh_devices(self._pending_guid)
        self.axes_panel.setVisible(controller)
        self.source_hint.setVisible(not controller)
        self.forza_port_row.setVisible(source == "game")
        self.f1_port_row.setVisible(source == "game")
        if not controller:
            self.source_hint.setText(self._t(f"source_hint_{source}"))
        self._fit_height()

    def _start_axis_learning(self, axis: str) -> None:
        self._stop_axis_learning()
        chosen = self.device_combo.currentData() or ""
        try:
            baseline = self.controller.axis_samples(chosen)
        except (OSError, ValueError):
            baseline = {}
        if not baseline:
            self.learn_hint.setText(self._t("detect_no_device"))
            return
        self._axis_detector = AxisDetector(baseline)
        self._learning_axis = axis
        self._learn_started = time.monotonic()
        self.learn_buttons[axis].setText(self._t("detecting"))
        self.learn_hint.setText(self._t("detect_prompt", axis=self._t(axis)))
        self._learn_timer.start()

    def _stop_axis_learning(self) -> None:
        self._learn_timer.stop()
        if self._learning_axis is not None:
            self.learn_buttons[self._learning_axis].setText(self._t("detect_axis"))
        self._learning_axis = None
        self._axis_detector = None

    def _poll_axis(self) -> None:
        axis = self._learning_axis
        detector = self._axis_detector
        if axis is None or detector is None:
            return
        if time.monotonic() - self._learn_started > 8:
            self._stop_axis_learning()
            self.learn_hint.setText(self._t("detect_timeout"))
            return
        chosen = self.device_combo.currentData() or ""
        try:
            found = detector.feed(self.controller.axis_samples(chosen))
        except (OSError, ValueError):
            self._stop_axis_learning()
            self.learn_hint.setText(self._t("detect_no_device"))
            return
        if found is None:
            return
        device_id, index, inverted = found
        self._stop_axis_learning()
        if self.device_combo.findData(device_id) < 0:
            self._refresh_devices(device_id)
        self.device_combo.setCurrentIndex(self.device_combo.findData(device_id))
        self.axes[axis].setCurrentIndex(self.axes[axis].findData(index))
        if axis != "steer":
            self.inverts[axis].setChecked(inverted)
        self.learn_hint.setText(self._t("detected_axis", axis=self._t(axis), name=AXIS_NAMES[index]))

    def closeEvent(self, event) -> None:  # noqa: N802
        self._stop_axis_learning()
        super().closeEvent(event)

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
            avoid_trace_overlap=self.avoid_trace_overlap.isChecked(),
            smoothing_ms=self.smooth_slider.value(),
            opacity=self.opacity_slider.value(),
            steering_lock_deg=self.steering_slider.value(),
            update_hz=self.rate_combo.currentData(),
            forza_port=self.forza_port.value(),
            f1_port=self.f1_port.value(),
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
            show_pedal_values=self.show_pedal_values.isChecked(),
            show_history=self.show_history.isChecked(),
            show_gas=self.show_gas.isChecked(),
            show_brake=self.show_brake.isChecked(),
            show_info_bar=self.show_info_bar.isChecked(),
            wheel_style=self.wheel_combo.currentData(),
            safe_inset=self.safe_slider.value(),
            info_position=self.info_combo.currentData(),
            language=self.language_combo.currentData(),
        )
        self.accept()
