"""Shared utilities: paths, single-instance check."""

import os
import sys


def get_app_dir() -> str:
    """Return the directory containing the application (works with PyInstaller)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_data_dir() -> str:
    """Return the data/ directory for daily stats files."""
    d = os.path.join(get_app_dir(), "data")
    os.makedirs(d, exist_ok=True)
    return d


def get_config_path() -> str:
    """Return the path to config.json."""
    return os.path.join(get_app_dir(), "config.json")


def get_resources_dir() -> str:
    """Return the resources/ directory."""
    d = os.path.join(get_app_dir(), "resources")
    os.makedirs(d, exist_ok=True)
    return d


def get_icon_path() -> str:
    """Return the path to the app icon PNG."""
    return os.path.join(get_resources_dir(), "icon.png")
