"""Global keyboard / mouse listeners via pynput, with thread-safe QObject signals."""

from __future__ import annotations

import threading
from datetime import date

from PySide6.QtCore import QObject, Signal

from pynput.keyboard import Listener as KbListener
from pynput.mouse import Listener as MsListener

from .data_manager import DataManager


class InputHooks(QObject):
    """Listens for ALL keyboard presses and mouse clicks system-wide.

    Emits ``count_updated`` on each event so the UI can update in real time.
    Periodic flushes to disk are managed externally (via a QTimer in main).
    """

    count_updated = Signal(dict)  # payload: {"keyboard": int, "mouse": int}
    rollover_detected = Signal()  # queued to the Qt main thread

    def __init__(self, data_manager: DataManager, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._data = data_manager
        self._lock = threading.Lock()
        self._pending_rollovers: list[dict] = []

        # Restore today's saved counts
        saved = self._data.load_today()
        self.keyboard_count: int = saved["keyboard"]
        self.mouse_count: int = saved["mouse"]

        # The calendar day these counters belong to; rollover resets on day change.
        self._stat_date: str = date.today().isoformat()

        # Start pynput listeners (daemon threads)
        self._kb_listener = KbListener(on_press=self._on_key_press)
        self._ms_listener = MsListener(on_click=self._on_mouse_click)
        self._kb_listener.start()
        self._ms_listener.start()

    # ------------------------------------------------------------------
    # pynput callbacks (run on pynput's internal threads)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Day rollover
    # ------------------------------------------------------------------

    def rollover_if_needed(self) -> dict | None:
        """Atomically switch counters to today and queue the sealed snapshot.

        The caller may run on a pynput thread, so this method never performs
        disk I/O. Sealed snapshots remain queued until the Qt main thread
        drains them, including during the final application flush.
        """
        with self._lock:
            today = date.today().isoformat()
            if today == self._stat_date:
                return None
            snapshot: dict = {
                "date": self._stat_date,
                "keyboard": self.keyboard_count,
                "mouse": self.mouse_count,
            }
            self._pending_rollovers.append(snapshot)
            self._stat_date = today
            self.keyboard_count = 0
            self.mouse_count = 0
        self.count_updated.emit({"keyboard": 0, "mouse": 0})
        return snapshot

    def drain_rollovers(self) -> list[dict]:
        """Return and clear all sealed day snapshots awaiting persistence."""
        with self._lock:
            snapshots = self._pending_rollovers
            self._pending_rollovers = []
        return snapshots

    def current_snapshot(self) -> dict:
        """Return a consistent copy of the active date and both counters."""
        with self._lock:
            return {
                "date": self._stat_date,
                "keyboard": self.keyboard_count,
                "mouse": self.mouse_count,
            }

    def _on_key_press(self, key) -> None:
        if self.rollover_if_needed() is not None:
            self.rollover_detected.emit()
        with self._lock:
            self.keyboard_count += 1
            kb = self.keyboard_count
            ms = self.mouse_count
        self.count_updated.emit({"keyboard": kb, "mouse": ms})

    def _on_mouse_click(self, _x, _y, _button, pressed) -> None:
        if not pressed:
            return
        if self.rollover_if_needed() is not None:
            self.rollover_detected.emit()
        with self._lock:
            self.mouse_count += 1
            kb = self.keyboard_count
            ms = self.mouse_count
        self.count_updated.emit({"keyboard": kb, "mouse": ms})

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Stop both listeners. Safe to call multiple times."""
        try:
            self._kb_listener.stop()
        except Exception:
            pass
        try:
            self._ms_listener.stop()
        except Exception:
            pass
