#!/usr/bin/env python
"""Validate an OKF bundle. Exit code 0 = pass, 1 = validation errors.

Usage: python scripts/validate_okf.py --input ./data/okf [-v]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from codeknowledge.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["validate", *sys.argv[1:]]))
