#!/usr/bin/env python
"""Load an OKF bundle and print the ingestion report.

Usage: python scripts/ingest_okf.py --input ./data/okf [-v]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from codeknowledge.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["ingest", *sys.argv[1:]]))
