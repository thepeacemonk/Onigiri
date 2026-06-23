#!/usr/bin/env python3
"""
Zero-dependency runner for Onigiri's Tier 1 suite.

This box has no pip/pytest (Python is externally managed), so this runner lets
the pure-logic tests run with nothing but the system Python. It applies the same
tests/conftest.py stubs that pytest would, and the suite stays fully
pytest-compatible: anywhere pytest *is* available (e.g. CI), plain `pytest` runs
the identical tests with no changes.

    python3 tests/run.py
"""

import importlib
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# Side effects only: stub `aqt` and fake the `onigiri` siblings before any test
# module imports the engine. This is exactly what pytest loads from conftest.py.
import conftest  # noqa: F401,E402

TEST_MODULES = ["test_special_days"]


def main():
    passed, failures = 0, []
    for mod_name in TEST_MODULES:
        module = importlib.import_module(mod_name)
        tests = [
            (name, obj)
            for name, obj in vars(module).items()
            if name.startswith("test_") and callable(obj)
        ]
        for name, fn in tests:
            try:
                fn()
            except Exception:  # AssertionError or anything else == failure
                failures.append((f"{mod_name}::{name}", traceback.format_exc()))
                sys.stdout.write("F")
            else:
                passed += 1
                sys.stdout.write(".")
            sys.stdout.flush()

    print("\n")
    for label, tb in failures:
        print(f"FAILED {label}\n{tb}")
    total = passed + len(failures)
    print(f"{passed}/{total} passed, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
