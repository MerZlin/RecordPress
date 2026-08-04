"""Background QThread that polls CPU / memory / GPU periodically."""

from __future__ import annotations

import psutil
from PySide6.QtCore import QThread, Signal

from .gpu_monitor import GpuMonitor


class StatsCollector(QThread):
    """Polls psutil (CPU, memory) and GpuMonitor every N ms, emits results."""

    stats_updated = Signal(dict)  # payload: {"cpu": float, "memory": float, "gpu": float, "disk": float}

    def __init__(self, interval_ms: int = 1000, parent=None) -> None:
        super().__init__(parent)
        self._interval_ms = interval_ms
        self._running = False
        self._gpu = GpuMonitor()

    def run(self) -> None:
        self._running = True
        tick = 0
        cached_gpu = 0.0

        # Prime psutil CPU percent (first call returns 0 otherwise)
        psutil.cpu_percent(interval=None)

        while self._running:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory().percent

            # GPU is slower — only poll every 5 ticks
            if tick % 5 == 0:
                try:
                    cached_gpu = self._gpu.get_usage()
                except Exception:
                    cached_gpu = 0.0

            disk_usage = psutil.disk_usage("C:\\")
            disk_free_gb = disk_usage.free / (1024 ** 3)

            self.stats_updated.emit(
                {"cpu": cpu, "memory": mem, "gpu": cached_gpu, "disk": disk_free_gb}
            )
            tick += 1
            self.msleep(self._interval_ms)

    def stop(self) -> None:
        self._running = False
        self.wait(3000)
