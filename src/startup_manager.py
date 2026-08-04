"""Windows startup registry helper — adds/removes the app from HKCU Run key."""

from __future__ import annotations

import sys
import winreg

REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "DesktopPet"


def is_packaged() -> bool:
    """True when running as a PyInstaller-built EXE."""
    return bool(getattr(sys, "frozen", False))


def is_startup_enabled() -> bool:
    """Check whether the app is registered to start on boot."""
    if not is_packaged():
        return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ
        )
        value, _ = winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return value == sys.executable
    except FileNotFoundError:
        return False


def set_startup(enable: bool) -> None:
    """Add or remove the app from the Windows startup registry key.

    Does nothing when running from source (not packaged).
    """
    if not is_packaged():
        return
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE
    )
    if enable:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, sys.executable)
    else:
        try:
            winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass
    winreg.CloseKey(key)
