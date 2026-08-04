"""User settings persistence with JSON + deep-merge defaults."""

import json
import os
import threading
from typing import Any

from .utils import get_config_path


class ConfigManager:
    """Load / save config.json with dotted-path access and default fallback."""

    DEFAULT_CONFIG: dict[str, Any] = {
        "display": {
            "keyboard": True,
            "mouse": True,
            "cpu": True,
            "memory": True,
            "gpu": False,
            "disk": False,
        },
        "font": {
            "family": "Microsoft YaHei",
            "size": 12,
        },
        "layout": {
            "mode": "default",   # "default" (vertical) | "horizontal" (single row)
        },
        "appearance": {
            "opacity": 0.88,          # 0.10 – 1.00
            "font_color": "#E8E8EC",  # hex
        },
        "window": {
            "x": None,
            "y": None,
            "width": 300,
            "height": 200,
        },
        "general": {
            "start_on_boot": False,
            "start_minimized": False,
            "lock_window": False,
            "always_on_top": True,
            "flush_interval_seconds": 10,
            "stats_poll_interval_ms": 1000,
        },
    }

    def __init__(self, config_path: str | None = None) -> None:
        self._path = config_path or get_config_path()
        self._lock = threading.Lock()
        self.data: dict[str, Any] = {}
        self.load()

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Read JSON from disk, deep-merge with defaults."""
        loaded: dict[str, Any] = {}
        if os.path.isfile(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
            except (json.JSONDecodeError, OSError):
                loaded = {}
        with self._lock:
            self.data = self._deep_merge(self.DEFAULT_CONFIG, loaded)

    def save(self) -> None:
        """Atomic write current config to disk."""
        tmp = self._path + ".tmp"
        with self._lock:
            try:
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(self.data, fh, ensure_ascii=False, indent=2)
                os.replace(tmp, self._path)
            except Exception:
                if os.path.isfile(tmp):
                    os.unlink(tmp)
                raise

    # ------------------------------------------------------------------
    # Access helpers
    # ------------------------------------------------------------------

    def _deep_merge(
        self, base: dict[str, Any], override: dict[str, Any]
    ) -> dict[str, Any]:
        """Recursively merge `override` into `base`, returning a new dict."""
        result = base.copy()
        for key, val in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(val, dict):
                result[key] = self._deep_merge(result[key], val)
            else:
                result[key] = val
        return result

    def get(self, dotted_path: str, default: Any = None) -> Any:
        """Read a config value by dotted path, e.g. 'display.cpu'."""
        with self._lock:
            node: Any = self.data
            for part in dotted_path.split("."):
                if not isinstance(node, dict) or part not in node:
                    return default
                node = node[part]
            return default if node is None else node

    def set(self, dotted_path: str, value: Any) -> None:
        """Write a config value by dotted path and persist."""
        with self._lock:
            parts = dotted_path.split(".")
            node: dict[str, Any] = self.data
            for part in parts[:-1]:
                if part not in node:
                    node[part] = {}
                node = node[part]  # type: ignore[assignment]
            node[parts[-1]] = value
        self.save()
