"""PyInstaller build script — produces a single-file Windows EXE (no console).

Usage:  python build.py
Output: dist/DesktopPet.exe
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


def build() -> None:
    root = os.path.dirname(os.path.abspath(__file__))

    # Ensure icon exists
    from src.icon_generator import generate_icon
    from src.utils import get_resources_dir, get_icon_path

    os.makedirs(get_resources_dir(), exist_ok=True)
    if not os.path.isfile(get_icon_path()):
        print("Generating icon…")
        generate_icon(get_icon_path())

    sep = ";" if sys.platform == "win32" else ":"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        # Output
        "--onefile",
        "--windowed",
        "--name", "DesktopPet",
        "--icon", get_icon_path(),
        "--add-data", f"resources/icon.png{sep}resources",
        # Suppress console / error popups
        "--disable-windowed-traceback",
        # pynput platform backends (PyInstaller often misses these)
        "--hidden-import", "pynput.keyboard._win32",
        "--hidden-import", "pynput.mouse._win32",
        # Qt modules that may be missed by auto-detection
        "--hidden-import", "PySide6.QtCore",
        "--hidden-import", "PySide6.QtGui",
        "--hidden-import", "PySide6.QtWidgets",
        # Collect all pynput submodules
        "--collect-submodules", "pynput",
        # Clean build
        "--clean",
        "--noconfirm",
        os.path.join(root, "main.py"),
    ]

    print("Running PyInstaller…")
    subprocess.run(cmd, check=True, cwd=root)

    # Clean up build artifacts (keep only dist/)
    build_dir = os.path.join(root, "build")
    spec_file = os.path.join(root, "DesktopPet.spec")
    if os.path.isdir(build_dir):
        shutil.rmtree(build_dir)
    if os.path.isfile(spec_file):
        os.remove(spec_file)

    exe = os.path.join(root, "dist", "DesktopPet.exe")
    print(f"Build complete → {exe}")


if __name__ == "__main__":
    build()
