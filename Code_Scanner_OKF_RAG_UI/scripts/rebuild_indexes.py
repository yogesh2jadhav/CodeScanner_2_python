#!/usr/bin/env python
"""Rebuild graph + vector indexes from the OKF bundle (indexes are derived and disposable).

Usage: python scripts/rebuild_indexes.py [--input ./data/okf] [--skip-vectors]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from codeknowledge.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["rebuild", *sys.argv[1:]]))
