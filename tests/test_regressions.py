"""Regression tests for topmost and midnight rollover bugs."""

from __future__ import annotations

import ctypes
import os
import tempfile
import unittest
from datetime import date as real_date
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from main import DesktopPetApp
from src.config_manager import ConfigManager
from src.desktop_widget import DesktopWidget
from src.input_hooks import InputHooks


class _DummyListener:
    """Listener double that keeps callbacks but starts no global hooks."""

    def __init__(self, **callbacks) -> None:
        self.callbacks = callbacks
        self.started = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False


class _FakeDate:
    current = real_date(2026, 8, 26)

    @classmethod
    def today(cls):
        return cls.current


class _RecordingDataManager:
    def __init__(self, keyboard: int = 12, mouse: int = 7) -> None:
        self.keyboard = keyboard
        self.mouse = mouse
        self.saved_days: list[tuple[str, int, int]] = []

    def load_today(self) -> dict[str, int]:
        return {"keyboard": self.keyboard, "mouse": self.mouse}

    def save_day(self, iso_date: str, keyboard: int, mouse: int) -> None:
        self.saved_days.append((iso_date, keyboard, mouse))


class TopmostRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        config_path = os.path.join(self.temp_dir.name, "config.json")
        self.config = ConfigManager(config_path=config_path)
        self.widget = DesktopWidget(self.config)

    def tearDown(self) -> None:
        self.widget.hide()
        self.widget.deleteLater()
        self.app.processEvents()
        self.temp_dir.cleanup()

    def test_reasserts_native_topmost_even_when_qt_flag_is_already_set(self) -> None:
        """Catches the early return that leaves a stale native Z-order untouched."""
        with mock.patch.object(
            ctypes.windll.user32, "SetWindowPos", return_value=1
        ) as set_window_pos:
            self.widget.set_always_on_top(True)

        self.assertGreaterEqual(set_window_pos.call_count, 1)

    def test_showing_widget_reasserts_native_topmost(self) -> None:
        """Catches tray restore paths that show without repairing native TOPMOST."""
        self.widget.hide()
        with mock.patch.object(
            ctypes.windll.user32, "SetWindowPos", return_value=1
        ) as set_window_pos:
            self.widget.show()
            self.app.processEvents()

        self.assertGreaterEqual(set_window_pos.call_count, 1)


class MidnightRolloverRegressionTests(unittest.TestCase):
    def test_periodic_flush_uses_the_date_owned_by_the_counter_snapshot(self) -> None:
        """Prevents a 00:00 race between rollover checking and save_today()."""

        class _SnapshotHooks:
            def rollover_if_needed(self):
                return None

            def drain_rollovers(self):
                return []

            def current_snapshot(self):
                return {"date": "2026-08-26", "keyboard": 41, "mouse": 13}

        class _SnapshotDataManager:
            def __init__(self):
                self.saved_days = []

            def save_day(self, iso_date, keyboard, mouse):
                self.saved_days.append((iso_date, keyboard, mouse))

            def save_today(self, keyboard, mouse):
                raise AssertionError("flush must not choose a second, unrelated date")

        data_manager = _SnapshotDataManager()
        app = DesktopPetApp.__new__(DesktopPetApp)
        app.input_hooks = _SnapshotHooks()
        app.data_manager = data_manager

        app._do_flush()

        self.assertEqual(
            [("2026-08-26", 41, 13)],
            data_manager.saved_days,
        )

    def test_first_input_after_midnight_preserves_yesterday_before_new_count(self) -> None:
        """Catches the discarded snapshot when pynput wins the midnight race."""
        data_manager = _RecordingDataManager(keyboard=12, mouse=7)
        _FakeDate.current = real_date(2026, 8, 26)

        with (
            mock.patch("src.input_hooks.KbListener", _DummyListener),
            mock.patch("src.input_hooks.MsListener", _DummyListener),
            mock.patch("src.input_hooks.date", _FakeDate),
        ):
            hooks = InputHooks(data_manager)
            app = DesktopPetApp.__new__(DesktopPetApp)
            app.input_hooks = hooks
            app.data_manager = data_manager

            _FakeDate.current = real_date(2026, 8, 27)
            hooks._on_key_press(None)
            app._handle_rollover()

        self.assertEqual(
            [("2026-08-26", 12, 7)],
            data_manager.saved_days,
        )
        self.assertEqual(1, hooks.keyboard_count)
        self.assertEqual(0, hooks.mouse_count)


if __name__ == "__main__":
    unittest.main()