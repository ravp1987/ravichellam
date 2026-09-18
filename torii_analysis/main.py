"""CLI entrypoint.

Usage:
  python main.py fetch     # pull data from the Torii API into data/raw/
  python main.py report    # analyze cached data and write report.html
  python main.py all       # fetch then report
"""
from __future__ import annotations

import sys

from fetch import fetch_all
from report import build_report


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("fetch", "all"):
        paths = fetch_all()
        for name, path in paths.items():
            print(f"fetched {name}: {path}")
    if cmd in ("report", "all"):
        path = build_report()
        print(f"report written to {path}")
    if cmd not in ("fetch", "report", "all"):
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
