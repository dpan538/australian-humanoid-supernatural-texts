#!/usr/bin/env python3
"""Run tests with pytest if available, otherwise use a tiny local fallback."""

from __future__ import annotations

import importlib.util
import inspect
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def run_fallback() -> int:
    failures = 0
    for test_path in sorted((ROOT / "tests").glob("test_*.py")):
        spec = importlib.util.spec_from_file_location(test_path.stem, test_path)
        if spec is None or spec.loader is None:
            print(f"Could not load {test_path}", file=sys.stderr)
            failures += 1
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name, func in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith("test_"):
                continue
            try:
                func()
                print(f"PASS {test_path.name}::{name}")
            except Exception:
                failures += 1
                print(f"FAIL {test_path.name}::{name}", file=sys.stderr)
                traceback.print_exc()
    return 1 if failures else 0


def main() -> None:
    try:
        import pytest  # type: ignore
    except Exception:
        raise SystemExit(run_fallback())
    raise SystemExit(pytest.main([str(ROOT / "tests")]))


if __name__ == "__main__":
    main()

