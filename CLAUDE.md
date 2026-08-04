# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

小桌宠 (Desktop Pet) — a Windows desktop overlay widget that tracks and displays:
- Today's keyboard press count
- Today's mouse click count
- CPU / Memory / GPU usage percentage

The app lives in the system tray; closing the desktop widget hides it to the tray, not exits. Data persists as daily JSON files in `data/` (under the app directory, not on C:).

## Tech Stack

- **Python 3** + **PySide6** (Qt for Python) for all UI
- **pynput** for global keyboard/mouse hooks (daemon threads, signal-safe)
- **psutil** for CPU/memory polling (QThread)
- **Pillow** for icon generation
- **WMI / nvidia-smi** for GPU usage (two-tier fallback; GPUtil intentionally excluded — see below)
- **PyInstaller** for single-file EXE packaging

## Design Principle: EXE-First

The packaged `dist/DesktopPet.exe` is **the** user-facing deliverable. All features MUST work through the GUI — users should never need a terminal. Design and test with the EXE as the target, not `python main.py`. `python` / `pythonw` are for development only.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app (with terminal — for debugging)
python main.py

# Run the app (no terminal — for normal use)
pythonw main.pyw
# or double-click main.pyw in Explorer

# Build single-file EXE
python build.py
# Output: dist/DesktopPet.exe
```

## Architecture

```
main.py                      # Entry point: QApplication, component assembly, signal wiring
src/
  desktop_widget.py          # Frameless always-on-top overlay, drag-to-move, edge-resize
  system_tray.py             # QSystemTrayIcon + right-click context menu
  menu_window.py             # Tabbed settings (checkboxes + font slider) + calendar tab
  calendar_widget.py         # Monthly calendar grid with DayBox cells showing K:/M: counts
  input_hooks.py             # pynput keyboard/mouse listeners → count_updated Signal
  stats_collector.py         # QThread polling psutil + GpuMonitor → stats_updated Signal
  gpu_monitor.py             # GPU usage: WMI → nvidia-smi → 0.0 fallback chain
  data_manager.py            # Daily JSON persistence (data/YYYY-MM-DD.json), atomic writes
  config_manager.py          # config.json with deep-merge defaults, dotted-path access
  startup_manager.py         # HKCU Run-key registration for boot-start (packaged EXE only)
  icon_generator.py          # Pillow-based multi-res icon (dark blue bg + white bar chart)
  utils.py                   # Path resolution (PyInstaller-aware), resource dirs
```

### Signal Flow

```
InputHooks.count_updated(dict)  ──→ DesktopWidget.update_counts(kb, ms)
StatsCollector.stats_updated(dict) ──→ DesktopWidget.update_stats(cpu, mem, gpu)
SettingsTab.display_changed ──→ DesktopWidget.refresh_from_config()
SettingsTab.font_changed ──→ DesktopWidget.refresh_from_config()
SettingsTab.layout_changed ──→ DesktopWidget.refresh_from_config()
SettingsTab.appearance_changed ──→ DesktopWidget.refresh_from_config()
SettingsTab.lock_changed / topmost_changed ──→ DesktopWidget.refresh_from_config()
SettingsTab.position_requested(str) ──→ DesktopWidget.move_to_position()
QTimer(flush_interval_seconds).timeout ──→ DataManager.save_today()  [atomic write]
SystemTray.activated ──→ DesktopWidget.show/hide
SystemTray context menu ──→ MenuWindow.show / exit
```

### Threading Model

- **Main thread**: Qt event loop, all UI
- **StatsCollector (QThread)**: polls psutil every `stats_poll_interval_ms` (default 1000ms), GPU every 5 ticks, emits Signal
- **pynput listeners (daemon threads)**: callbacks emit Signal (Qt queues cross-thread automatically)
- **DataManager**: writes protected by `threading.Lock`; flush timer runs on main thread
- **Startup registry**: `startup_manager` reads/writes HKCU Run key; no-op when running from source

## Key Design Decisions

- **closeEvent → hide**: DesktopWidget and MenuWindow both override `closeEvent` to `event.ignore(); self.hide()` so they never actually close. Only "Exit" in the tray menu truly quits.
- **Atomic writes**: DataManager writes to a temp file then `os.replace()` to the target path — prevents corruption on crash.
- **Config deep-merge**: Defaults are merged with user config on load, so adding new keys in future versions won't break existing user settings.
- **GPU fallback chain**: WMI performance counters → `nvidia-smi` subprocess (with `CREATE_NO_WINDOW`) → 0.0. GPUtil is intentionally NOT used — it calls nvidia-smi internally without `CREATE_NO_WINDOW`, which causes console flashes in the packaged EXE.
- **Font size presets**: 5 snapping stops on the slider: 8, 12, 16, 20, 24.
- **Window resize on frameless widget**: Manual edge detection (6px border zone) with compass-direction cursor changes + mouse-drag geometry updates.
- **Single-instance not enforced**: Currently allows multiple instances. If needed, add `QSharedMemory` check in `main.py`.

## Data Files

- `config.json` — user settings (created on first change, not on first run)
- `data/YYYY-MM-DD.json` — daily keyboard/mouse counts, format:
  ```json
  {"date": "2026-07-26", "keyboard_count": 4821, "mouse_count": 1347}
  ```
- `resources/icon.png` — generated on first run if missing

## Potential Issues

- **pynput** may require admin privileges for global hooks on some Windows configurations.
- **GPU monitoring** may show 0% on systems without discrete NVIDIA GPU (falls back gracefully).
- **PyInstaller** needs explicit `--hidden-import pynput.keyboard._win32` and `pynput.mouse._win32` or the built EXE will fail to start hooks.
- On Windows, PyInstaller `--add-data` uses `;` as separator (not `:` like Linux/macOS).
