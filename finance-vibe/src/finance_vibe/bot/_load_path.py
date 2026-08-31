"""Bootstrap src/ onto sys.path — loaded via importlib, not as finance_vibe.*"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_bootstrap_file = Path(__file__).resolve().parent / "_bootstrap.py"
_spec = importlib.util.spec_from_file_location("_fv_bootstrap", _bootstrap_file)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Cannot load {_bootstrap_file}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
