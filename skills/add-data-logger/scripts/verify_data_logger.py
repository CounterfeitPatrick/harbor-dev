#!/usr/bin/env python3
"""
Verify a rendered data_logger.py works end-to-end under mocked backends.

Used by /add-data-logger skill (Step 2.5) immediately after rendering, and by
the CI-style test_render_data_logger.py to sweep all configurations.

Mocks tensorboardX + wandb so no real installs / network are required. Imports
the rendered module from `--path`, instantiates DataLogger with whatever
backends were generated, and exercises every public method present.

Usage:
    python3 verify_data_logger.py --path /abs/path/to/data_logger.py

Exit codes:
    0 — all checks passed
    1 — import / instantiate / runtime error
    2 — invocation error (bad args)
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import numpy as np


def _detect_features(src: str) -> dict[str, bool]:
    """Inspect the rendered source to figure out which features it actually has."""
    return {
        "USE_TB":    "tensorboardX" in src,
        "USE_WANDB": "import wandb" in src or "self._wandb_logger" in src,
        "LOG_IMAGE": "_log_image" in src,
        "LOG_TEXT":  "def log_text" in src,
    }


def _install_mocks() -> None:
    """Install fake tensorboardX + wandb in sys.modules before import."""
    sys.modules["tensorboardX"] = MagicMock(name="tensorboardX_mock")
    sys.modules["wandb"] = MagicMock(name="wandb_mock")


def _load_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("rendered_data_logger", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("could not create import spec for {}".format(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(path: Path) -> int:
    src = path.read_text()

    # 1. Static parse — already done by ast.parse, but compile() catches more.
    try:
        compile(src, str(path), "exec")
    except SyntaxError as e:
        print("[FAIL] compile error: {}".format(e))
        return 1

    # 2. No leftover mustache markers
    leftover = re.findall(r"\{\{[^}]+\}\}", src)
    if leftover:
        print("[FAIL] unprocessed mustache markers: {}".format(set(leftover)))
        return 1

    # 3. Mocked import + instantiate
    feats = _detect_features(src)
    _install_mocks()
    try:
        mod = _load_module(path)
    except Exception as e:
        print("[FAIL] import: {}".format(e))
        return 1

    if not hasattr(mod, "DataLogger"):
        print("[FAIL] rendered module has no DataLogger class")
        return 1

    DL = mod.DataLogger

    # Build kwargs based on detected features
    init_kwargs = {"log_dir": "/tmp/.dl_verify_logs"}
    if feats["USE_TB"]:
        init_kwargs["log_tb"] = True
    if feats["USE_WANDB"]:
        init_kwargs.update({
            "log_wandb": True,
            "project": "verify",
            "run_name": "r1",
            "entity": "me",
            "wandb_init_retries": 1,
            "wandb_init_backoff_seconds": 0,
        })

    try:
        dl = DL(**init_kwargs)
    except Exception as e:
        print("[FAIL] DataLogger instantiation: {}".format(e))
        return 1

    # 4. Exercise public API.
    try:
        # scalar (always present)
        dl.record("loss", 0.5, step=0, log_stats=True)
        dl.record("loss", 0.3, step=1)
        dl.record_dict({"acc": 0.9, "lr": 1e-3}, step=1)

        if feats["LOG_IMAGE"]:
            img = np.zeros((4, 4, 3), dtype=np.uint8)
            dl.record("frame", img, step=0, data_type="image")

        if feats["LOG_TEXT"]:
            dl.log_text("note", "step 0 done", step=0)

        stats = dl.get_stats("loss")
        if not (abs(stats["mean"] - 0.4) < 1e-9 and stats["min"] == 0.3 and stats["max"] == 0.5):
            print("[FAIL] get_stats mismatch: {}".format(stats))
            return 1

        dl.close()
    except Exception as e:
        print("[FAIL] runtime error: {}".format(e))
        return 1

    # 5. Backend writes actually happened (via mocks)
    if feats["USE_TB"]:
        if not dl._tb_logger.add_scalar.called:
            print("[FAIL] TB add_scalar never called")
            return 1
        if feats["LOG_IMAGE"] and not dl._tb_logger.add_images.called:
            print("[FAIL] TB add_images never called")
            return 1
        if feats["LOG_TEXT"] and not dl._tb_logger.add_text.called:
            print("[FAIL] TB add_text never called")
            return 1
    if feats["USE_WANDB"]:
        if not dl._wandb_logger.log.called:
            print("[FAIL] wandb log never called")
            return 1

    feat_names = [k.replace("USE_", "").replace("LOG_", "").lower() for k, v in feats.items() if v]
    print("[OK] {} (features: {})".format(path.name, ",".join(feat_names) or "scalar-only"))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", required=True, help="absolute path to a rendered data_logger.py")
    args = ap.parse_args()

    p = Path(args.path).resolve()
    if not p.is_file():
        print("[FAIL] path does not exist: {}".format(p))
        return 2
    return _run(p)


if __name__ == "__main__":
    sys.exit(main())
