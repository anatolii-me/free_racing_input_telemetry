from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from acc_trace.config import Settings, settings_path


class PortableSettingsTests(unittest.TestCase):
    def test_frozen_app_saves_settings_beside_executable(self) -> None:
        with TemporaryDirectory() as directory:
            executable = Path(directory) / "ACC-Trace.exe"
            with patch.object(sys, "frozen", True, create=True), \
                 patch.object(sys, "executable", str(executable)):
                self.assertEqual(settings_path(), executable.resolve().parent / "settings.json")
                settings = Settings(language="en", wheel_style="sport")
                settings.save()
                self.assertEqual(Settings.load().language, "en")
                self.assertEqual(Settings.load().wheel_style, "sport")

    def test_python_launch_keeps_appdata_settings(self) -> None:
        with TemporaryDirectory() as directory:
            with patch.object(sys, "frozen", False, create=True), \
                 patch.dict(os.environ, {"APPDATA": directory}):
                self.assertEqual(settings_path(), Path(directory) / "ACC Trace" / "settings.json")


if __name__ == "__main__":
    unittest.main()
