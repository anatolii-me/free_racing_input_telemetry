from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import QPoint, QTimer
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .config import Settings
from .i18n import tr
from .overlay import Overlay, paint_icon
from .settings_dialog import SettingsDialog


class TraceApp:
    def __init__(self, app: QApplication, settings: Settings) -> None:
        self.app = app
        self.settings = settings
        self.overlay = Overlay(settings)
        self.dialog: SettingsDialog | None = None
        self.overlay.settings_requested.connect(self.open_settings)
        self.overlay.close_requested.connect(app.quit)
        self.overlay.position_changed.connect(self.save_position)
        self.tray = QSystemTrayIcon(QIcon(paint_icon()), app)
        menu = QMenu()
        self.show_action = menu.addAction("")
        self.show_action.triggered.connect(self.show_overlay)
        self.settings_action = menu.addAction("")
        self.settings_action.triggered.connect(self.open_settings)
        menu.addSeparator()
        self.quit_action = menu.addAction("")
        self.quit_action.triggered.connect(app.quit)
        self._translate_menu()
        self.overlay.context_menu_requested.connect(menu.exec)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("ACC Trace")
        self.tray.activated.connect(self._tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        self._place_overlay()
        self.overlay.show()

    def _place_overlay(self) -> None:
        if self.settings.x is not None and self.settings.y is not None:
            candidate = self.overlay.geometry()
            candidate.moveTopLeft(QPoint(self.settings.x, self.settings.y))
            if any(screen.availableGeometry().intersects(candidate) for screen in QGuiApplication.screens()):
                self.overlay.move(self.settings.x, self.settings.y)
                return
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.overlay.move(area.right() - self.overlay.width() - 24, area.bottom() - self.overlay.height() - 24)

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.show_overlay()

    def show_overlay(self) -> None:
        self.overlay.show()
        self.overlay.raise_()

    def _translate_menu(self) -> None:
        language = self.settings.language
        self.show_action.setText(tr(language, "show_overlay"))
        self.settings_action.setText(tr(language, "settings") + "…")
        self.quit_action.setText(tr(language, "quit"))

    def save_position(self, x: int, y: int) -> None:
        self.settings.x = x
        self.settings.y = y
        self.settings.save()

    def open_settings(self) -> None:
        if self.dialog is not None and self.dialog.isVisible():
            self.dialog.raise_()
            self.dialog.activateWindow()
            return
        self.dialog = SettingsDialog(self.settings, self.overlay.controller_reader)
        self.dialog.accepted.connect(self._settings_accepted)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def _settings_accepted(self) -> None:
        if self.dialog is None:
            return
        self.settings = self.dialog.result_settings
        self.settings.save()
        self.overlay.apply_settings(self.settings)
        self._translate_menu()
        self.dialog = None


def main() -> int:
    parser = argparse.ArgumentParser(description="ACC Trace telemetry overlay")
    parser.add_argument("--demo", action="store_true", help="show generated sample telemetry")
    parser.add_argument("--screenshot", help="save a prototype preview PNG and exit")
    parser.add_argument("--screenshot-settings", help="save a settings preview PNG and exit")
    args = parser.parse_args()

    app = QApplication(sys.argv[:1])
    app.setApplicationName("ACC Trace")
    app.setQuitOnLastWindowClosed(False)
    settings = Settings.load()
    if args.demo or args.screenshot or args.screenshot_settings:
        settings.source = "demo"
    trace = TraceApp(app, settings)
    if args.screenshot:
        def capture() -> None:
            trace.overlay.grab().save(args.screenshot)
            app.quit()
        QTimer.singleShot(3200, capture)
    if args.screenshot_settings:
        def capture_settings() -> None:
            trace.open_settings()
            QTimer.singleShot(200, lambda: (trace.dialog.grab().save(args.screenshot_settings), app.quit()))
        QTimer.singleShot(150, capture_settings)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
