#!/usr/bin/env python3
"""
CI-style smoke test for render_data_logger.py + data_logger.py.template.

Sweeps every (backend × features) combination, renders a temp file for each,
and pipes it through verify_data_logger.py. Fails on first error.

Run:
    python3 skills/add-data-logger/tests/test_render_data_logger.py
"""
from __future__ import annotations

import itertools
import subprocess
import sys
import tempfile
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[2]
RENDER = PLUGIN_ROOT / "skills/add-data-logger/scripts/render_data_logger.py"
VERIFY = PLUGIN_ROOT / "skills/add-data-logger/scripts/verify_data_logger.py"


def _powerset(items):
    for r in range(0, len(items) + 1):
        for combo in itertools.combinations(items, r):
            yield combo


def main() -> int:
    backends = ["tb", "wandb", "both"]
    optional_features = ["image", "text"]

    n_total = 0
    n_pass = 0
    failures = []

    with tempfile.TemporaryDirectory() as td:
        td_p = Path(td)
        for backend in backends:
            for opt_combo in _powerset(optional_features):
                features_list = ["scalar"] + list(opt_combo)
                features_str = ",".join(features_list)
                tag = "{}__{}".format(backend, "_".join(features_list))
                out_path = td_p / "data_logger_{}.py".format(tag)

                n_total += 1
                # 1. Render
                r = subprocess.run(
                    [sys.executable, str(RENDER),
                     "--backend", backend,
                     "--features", features_str,
                     "--output", str(out_path)],
                    capture_output=True, text=True,
                )
                if r.returncode != 0:
                    failures.append((tag, "render", r.stderr.strip() or r.stdout.strip()))
                    print("[RENDER FAIL] {}".format(tag))
                    continue

                # 2. Verify
                v = subprocess.run(
                    [sys.executable, str(VERIFY), "--path", str(out_path)],
                    capture_output=True, text=True,
                )
                if v.returncode != 0:
                    failures.append((tag, "verify", v.stdout.strip() or v.stderr.strip()))
                    print("[VERIFY FAIL] {}: {}".format(tag, v.stdout.strip()))
                    continue

                n_pass += 1
                print("  [{:2}/{:2}] {}: {}".format(n_pass, n_total, tag, v.stdout.strip()))

    print()
    print("=" * 60)
    print("Summary: {}/{} configurations passed".format(n_pass, n_total))
    if failures:
        print()
        print("Failures:")
        for tag, stage, msg in failures:
            print("  - {} ({}): {}".format(tag, stage, msg[:200]))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
