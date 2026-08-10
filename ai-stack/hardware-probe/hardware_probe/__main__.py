"""CLI: `python3 -m hardware_probe [--pretty]`"""
import argparse
import json
import sys

from .probe import run_probe


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Navigator OS hardware probe — produces an AI model tier report."
    )
    parser.add_argument(
        "--pretty", action="store_true", help="Print the JSON output indented"
    )
    args = parser.parse_args()

    report = run_probe()
    print(json.dumps(report, indent=2 if args.pretty else None, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
