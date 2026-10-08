"""Adds Python/Source to sys.path so scripts in this folder can `from scene import ...`."""

import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent / "Source"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))
