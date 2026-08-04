"""GPU usage monitor with fallback chain: WMI → nvidia-smi → 0.

GPUtil is intentionally NOT used here — it calls nvidia-smi internally via
subprocess WITHOUT CREATE_NO_WINDOW, which causes a console flash on Windows.
We call nvidia-smi directly with the correct creationflags instead.
"""

from __future__ import annotations

import subprocess
import sys


class GpuMonitor:
    """Return GPU usage as a float percentage, or 0.0 if unavailable."""

    _METHOD: str | None = None  # cached method name after first successful call

    @classmethod
    def get_usage(cls) -> float:
        """Return GPU utilisation 0-100, trying each backend once."""
        if cls._METHOD is None:
            cls._METHOD = cls._detect_method()
        return cls._call_method(cls._METHOD)

    # ------------------------------------------------------------------
    # Detection (called once)
    # ------------------------------------------------------------------

    @classmethod
    def _detect_method(cls) -> str:
        """Try each backend in order; return the first working method name."""
        for name in ("wmi", "nvidia_smi"):
            try:
                val = cls._call_method(name)
                if val >= 0:
                    return name
            except Exception:
                continue
        return "none"

    # ------------------------------------------------------------------
    # Method dispatch
    # ------------------------------------------------------------------

    @classmethod
    def _call_method(cls, name: str) -> float:
        if name == "wmi":
            return cls._via_wmi()
        elif name == "nvidia_smi":
            return cls._via_nvidia_smi()
        else:
            return 0.0

    # ------------------------------------------------------------------
    # Backends
    # ------------------------------------------------------------------

    @staticmethod
    def _via_wmi() -> float:
        """Query GPU usage via Windows WMI performance counters.

        Uses a late import so the wmi package is only needed if this
        backend actually runs (it won't on systems without it).
        """
        import wmi  # type: ignore[import-untyped]

        c = wmi.WMI(namespace="root\\cimv2")
        engines = c.query(
            "SELECT * FROM Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine"
        )
        total = 0.0
        count = 0
        for eng in engines:
            try:
                total += float(eng.UtilizationPercentage)
                count += 1
            except (ValueError, AttributeError):
                pass
        if count > 0:
            return total / count
        return 0.0

    @staticmethod
    def _via_nvidia_smi() -> float:
        """Query nvidia-smi directly with console window suppressed."""
        creationflags = 0
        if sys.platform == "win32":
            creationflags = (
                subprocess.CREATE_NO_WINDOW
                | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=creationflags,
        )
        if result.returncode != 0:
            return 0.0
        try:
            line = result.stdout.strip().split("\n")[0].strip()
            return float(line)
        except (ValueError, IndexError):
            return 0.0
