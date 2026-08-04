"""Launcher that runs without a console window (via pythonw.exe on Windows).

Use this file to start the app without a terminal window.
Double-click main.pyw in Explorer, or run: pythonw main.pyw
"""

import os
import sys

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import main

if __name__ == "__main__":
    main()
