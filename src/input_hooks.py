"""Global keyboard / mouse listeners via pynput, with thread-safe QObject signals."""

from __future__ import annotations

import threading

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

    def __init__(self, data_manager: DataManager, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._data = data_manager
        self._lock = threading.Lock()

        # Restore today's saved counts
        saved = self._data.load_today()
        self.keyboard_count: int = saved["keyboard"]
        self.mouse_count: int = saved["mouse"]

        # Start pynput listeners (daemon threads)
        self._kb_listener = KbListener(on_press=self._on_key_press)
        self._ms_listener = MsListener(on_click=self._on_mouse_click)
        self._kb_listener.start()
        self._ms_listener.start()

    # ------------------------------------------------------------------
    # pynput callbacks (run on pynput's internal threads)
    # ------------------------------------------------------------------

    def _on_key_press(self, key) -> None:
        with self._lock:
            self.keyboard_count += 1
            kb = self.keyboard_count
            ms = self.mouse_count
        self.count_updated.emit({"keyboard": kb, "mouse": ms})

    def _on_mouse_click(self, _x, _y, _button, pressed) -> None:
        if not pressed:
            return
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
