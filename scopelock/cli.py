from __future__ import annotations

import argparse
import json

from .demo import run_demo


def main() -> None:
    parser = argparse.ArgumentParser(prog="scopelock", description="Run the local ScopeLock policy gateway demo")
    parser.add_argument("--db", default="scopelock.db", help="SQLite audit log path")
    parser.add_argument("--json", help="optional report output path")
    args = parser.parse_args()
    report = run_demo(args.db)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")


if __name__ == "__main__":
    main()
