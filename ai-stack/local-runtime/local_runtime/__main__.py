"""CLI: `python3 -m local_runtime [--pretty] [--hardware-probe-path PATH]`"""
import argparse
import json
import sys

from .status import build_status_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Navigator OS yerel model runtime durumu (Ollama + hardware tier)."
    )
    parser.add_argument("--pretty", action="store_true", help="JSON çıktısını girintili yazdır")
    parser.add_argument(
        "--hardware-probe-path",
        default="../hardware-probe",
        help="ai-stack/hardware-probe dizininin yolu (varsayılan: ../hardware-probe)",
    )
    args = parser.parse_args()

    try:
        report = build_status_report(hardware_probe_cwd=args.hardware_probe_path)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2 if args.pretty else None, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
