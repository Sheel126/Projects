"""Add project src/ to sys.path when bot CLI scripts are run directly."""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2]
_SRC_STR = str(_SRC)
if _SRC_STR not in sys.path:
    sys.path.insert(0, _SRC_STR)

PROJECT_ROOT = _SRC.parent
