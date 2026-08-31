"""Bootstrap sys.path then run a bot CLI script. Used by root launchers."""
from __future__ import annotations

import importlib.util
import runpy
import sys
from pathlib import Path
from types import ModuleType


def bootstrap() -> Path:
    bot_dir = Path(__file__).resolve().parent / "src" / "finance_vibe" / "bot"
    loader = bot_dir / "_load_path.py"
    spec = importlib.util.spec_from_file_location("fv_load_path", loader)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {loader}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return bot_dir.parent.parent.parent  # project root


def run_bot_script(relative: str, argv: list[str] | None = None) -> int:
    root = bootstrap()
    script = root / "src" / "finance_vibe" / "bot" / relative
    if not script.exists():
        print(f"Script not found: {script}", file=sys.stderr)
        return 1
    old_argv = sys.argv
    sys.argv = [str(script)] + (argv or [])
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0
    finally:
        sys.argv = old_argv
    return 0
