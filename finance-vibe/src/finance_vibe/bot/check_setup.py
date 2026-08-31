"""CLI: verify Alpaca, Ollama, and database before paper trading."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_lp = Path(__file__).resolve().parent / "_load_path.py"
_spec = importlib.util.spec_from_file_location("fv_load_path", _lp)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

import argparse
import json
import sys

from finance_vibe.bot.health import ping_ollama_chat, run_health_check


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify paper bot setup (Alpaca, Ollama, DB, schedule)",
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Also send a test chat request to Ollama (slower)",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args(argv)

    report = run_health_check()
    deep_ok = deep_msg = None

    if args.deep and report.services:
        ollama_svc = next((s for s in report.services if s.name == "Ollama"), None)
        if ollama_svc and ollama_svc.online:
            deep_ok, deep_msg = ping_ollama_chat()

    if args.json:
        out = report.to_dict()
        if args.deep:
            out["ollama_chat_test"] = {"ok": deep_ok, "detail": deep_msg}
        print(json.dumps(out, indent=2))
        return 0 if report.all_ready and (not args.deep or deep_ok) else 1

    print()
    print("=" * 60)
    print("  Finance-Vibe Paper Bot — Setup Check")
    print("=" * 60)
    print()
    print(f"  {report.headline}")
    print(f"  {report.subline}")
    print(f"  {report.next_event}")
    print(f"  Checked: {report.checked_at}")
    print()
    print("-" * 60)
    for svc in report.services:
        icon = "OK" if svc.online else "FAIL"
        print(f"  [{icon:4}] {svc.name:10}  {svc.message}")
        if svc.detail:
            for line in svc.detail.split(". "):
                if line.strip():
                    print(f"         {line.strip()}")
    print("-" * 60)

    if args.deep:
        print()
        if deep_ok:
            print(f"  [OK  ] Ollama chat test passed")
            print(f"         Response: {deep_msg}")
        else:
            print(f"  [FAIL] Ollama chat test failed")
            print(f"         {deep_msg}")
        print()

    if report.all_ready:
        print("  Ready for paper trading.")
        print("  Start all: .\\start-paper-bot.ps1")
        print()
        return 0 if (not args.deep or deep_ok) else 1

    print("  Fix the FAIL items above, then re-run this check.")
    print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
