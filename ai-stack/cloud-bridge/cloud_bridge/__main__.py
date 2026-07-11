"""CLI: `python3 -m cloud_bridge [--pretty]`"""
import argparse
import json
import sys

from .status import build_status_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Navigator OS cloud-bridge — Anthropic Claude API kimlik bilgisi durumu."
    )
    parser.add_argument("--pretty", action="store_true", help="JSON çıktısını girintili yazdır")
    args = parser.parse_args()

    report = build_status_report()
    print(json.dumps(report, indent=2 if args.pretty else None, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
