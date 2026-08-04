"""Daily stats persistence — one JSON file per day, atomic writes."""

import json
import os
import tempfile
import threading
from datetime import date, datetime
from typing import Any

from .utils import get_data_dir


class DataManager:
    """Manage daily keyboard / mouse count files under data/YYYY-MM-DD.json."""

    def __init__(self, data_dir: str | None = None) -> None:
        self._dir = data_dir or get_data_dir()
        os.makedirs(self._dir, exist_ok=True)
        self._write_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _filename_for(iso_date: str) -> str:
        return f"{iso_date}.json"

    def _path_for(self, iso_date: str) -> str:
        return os.path.join(self._dir, self._filename_for(iso_date))

    # ------------------------------------------------------------------
    # Atomic write
    # ------------------------------------------------------------------

    def _atomic_write(self, path: str, data: dict[str, Any]) -> None:
        fd, tmp = tempfile.mkstemp(dir=self._dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception:
            if os.path.isfile(tmp):
                os.unlink(tmp)
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_today(self) -> dict[str, int]:
        """Return today's saved counts, or zeros if no file yet."""
        return self.load_day(date.today().isoformat())

    def save_today(self, keyboard_count: int, mouse_count: int) -> None:
        """Persist today's running counts to disk (atomic)."""
        today = date.today().isoformat()
        payload: dict[str, Any] = {
            "date": today,
            "keyboard_count": keyboard_count,
            "mouse_count": mouse_count,
        }
        with self._write_lock:
            self._atomic_write(self._path_for(today), payload)

    def load_day(self, iso_date: str) -> dict[str, int]:
        """Return counts for an arbitrary date (or zeros)."""
        path = self._path_for(iso_date)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    obj = json.load(fh)
                return {
                    "keyboard": int(obj.get("keyboard_count", 0)),
                    "mouse": int(obj.get("mouse_count", 0)),
                }
            except (json.JSONDecodeError, OSError, ValueError):
                pass
        return {"keyboard": 0, "mouse": 0}

    def load_month_range(self, year: int, month: int) -> dict[str, dict[str, int]]:
        """Return {iso_date: {keyboard, mouse}} for every saved day in a month."""
        result: dict[str, dict[str, int]] = {}
        prefix = f"{year:04d}-{month:02d}-"
        try:
            for fname in os.listdir(self._dir):
                if not fname.startswith(prefix) or not fname.endswith(".json"):
                    continue
                iso = fname[:-5]  # strip ".json"
                result[iso] = self.load_day(iso)
        except OSError:
            pass
        return result

    def list_available_dates(self) -> list[str]:
        """Return sorted list of iso-date strings that have saved data."""
        dates: list[str] = []
        try:
            for fname in os.listdir(self._dir):
                if not fname.endswith(".json"):
                    continue
                stem = fname[:-5]
                try:
                    date.fromisoformat(stem)
                except ValueError:
                    continue  # not a YYYY-MM-DD stats file
                dates.append(stem)
        except OSError:
            pass
        dates.sort()
        return dates

    @staticmethod
    def today_str() -> str:
        return date.today().isoformat()
