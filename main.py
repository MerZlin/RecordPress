"""Desktop Pet (小桌宠) — entry point.

Keyboard / mouse counter + CPU / memory / GPU overlay for Windows.
Runs in the system tray; hides there instead of closing.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src.calendar_widget import CalendarWidget
from src.config_manager import ConfigManager
from src.data_manager import DataManager
from src.desktop_widget import DesktopWidget
from src.icon_generator import generate_icon
from src.input_hooks import InputHooks
from src.menu_window import MenuWindow
from src.startup_manager import is_startup_enabled, set_startup
from src.stats_collector import StatsCollector
from src.system_tray import SystemTray
from src.utils import get_icon_path


class DesktopPetApp:
    """Top-level application that owns all components and their wiring."""

    def __init__(self) -> None:
        self._app = QApplication(sys.argv)
        self._app.setApplicationName("DesktopPet")
        self._app.setOrganizationName("DesktopPet")
        self._app.setQuitOnLastWindowClosed(False)

        # Ensure icon exists
        self._ensure_icon()

        # Core services
        self.config = ConfigManager()
        self.data_manager = DataManager()

        # Sync registry startup state → config (user might have deleted the key manually)
        current = is_startup_enabled()
        if current != self.config.get("general.start_on_boot"):
            self.config.set("general.start_on_boot", current)

        # UI components
        self.desktop_widget = DesktopWidget(self.config)
        self.calendar_widget = CalendarWidget(self.data_manager)
        self.menu_window = MenuWindow(
            self.config, calendar_widget=self.calendar_widget
        )
        self.system_tray = SystemTray(
            self.desktop_widget,
            self.menu_window,
            on_exit_callback=self._on_exit,
        )

        # Data collectors
        self.input_hooks = InputHooks(self.data_manager)
        poll_ms = int(self.config.get("general.stats_poll_interval_ms", 1000))
        self.stats_collector = StatsCollector(interval_ms=max(poll_ms, 200))
        self.stats_collector.start()

        # --- Wire signals ---

        # Input hooks → desktop widget
        self.input_hooks.count_updated.connect(self._on_counts_updated)
        self.input_hooks.rollover_detected.connect(self._handle_rollover)
        # Push initial loaded counts to the widget
        self.desktop_widget.update_counts(
            self.input_hooks.keyboard_count,
            self.input_hooks.mouse_count,
        )

        # Stats collector → desktop widget
        self.stats_collector.stats_updated.connect(self.desktop_widget.update_stats)

        # Menu → desktop widget
        settings_tab = self.menu_window.settings_tab
        settings_tab.display_changed.connect(
            self.desktop_widget.refresh_from_config
        )
        settings_tab.font_changed.connect(
            lambda _: self.desktop_widget.refresh_from_config()
        )
        settings_tab.layout_changed.connect(
            self.desktop_widget.refresh_from_config
        )
        settings_tab.appearance_changed.connect(
            self.desktop_widget.refresh_from_config
        )
        settings_tab.position_requested.connect(
            self.desktop_widget.move_to_position
        )
        settings_tab.lock_changed.connect(
            self.desktop_widget.refresh_from_config
        )
        settings_tab.topmost_changed.connect(
            self.desktop_widget.refresh_from_config
        )

        # Periodic flush (configurable interval)
        flush_ms = int(self.config.get("general.flush_interval_seconds", 10)) * 1000
        self._flush_timer = QTimer()
        self._flush_timer.timeout.connect(self._do_flush)
        self._flush_timer.start(max(flush_ms, 5000))

        # Schedule a one-shot timer at the next midnight (day rollover)
        self._schedule_midnight()

        # Final flush on quit
        self._app.aboutToQuit.connect(self._on_about_to_quit)

        # Apply saved config state (lock, always_on_top, display, font, …)
        self.desktop_widget.refresh_from_config()

        # --- Show ---
        if not self.config.get("general.start_minimized", False):
            self.desktop_widget.show()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_icon() -> None:
        icon_path = get_icon_path()
        if not os.path.isfile(icon_path):
            generate_icon(icon_path)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_counts_updated(self, counts: dict) -> None:
        kb = counts.get("keyboard", 0)
        ms = counts.get("mouse", 0)
        self.desktop_widget.update_counts(kb, ms)

    def _do_flush(self) -> None:
        self._handle_rollover()
        snapshot = self.input_hooks.current_snapshot()
        self.data_manager.save_day(
            snapshot["date"], snapshot["keyboard"], snapshot["mouse"]
        )

    # ------------------------------------------------------------------
    # Midnight day rollover
    # ------------------------------------------------------------------

    def _handle_rollover(self) -> None:
        """Switch dates if needed and persist every sealed day snapshot."""
        self.input_hooks.rollover_if_needed()
        for snapshot in self.input_hooks.drain_rollovers():
            self.data_manager.save_day(
                snapshot["date"], snapshot["keyboard"], snapshot["mouse"]
            )

    def _schedule_midnight(self) -> None:
        """Re-arm a one-shot timer to fire at the next 00:00 local time."""
        now = datetime.now()
        next_midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        delay_ms = int((next_midnight - now).total_seconds() * 1000)
        QTimer.singleShot(delay_ms, self._on_midnight)

    def _on_midnight(self) -> None:
        """Midnight tick: seal yesterday's counts, reset, refresh UI, re-arm."""
        self._handle_rollover()
        self._schedule_midnight()

    def _on_exit(self) -> None:
        # aboutToQuit → _on_about_to_quit performs the final flush + cleanup.
        self._app.quit()

    def _on_about_to_quit(self) -> None:
        self._do_flush()
        self.input_hooks.stop()
        self.stats_collector.stop()

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self) -> int:
        return self._app.exec()


def main() -> None:
    app = DesktopPetApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
