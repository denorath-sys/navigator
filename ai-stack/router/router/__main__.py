"""CLI: `python3 -m router --prompt "..." [--prefer balanced|privacy|cost|speed] [--pretty]`"""
import argparse
import json
import sys

from .decision import PREFERENCES
from .status import route_request


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Navigator OS router — isteği yerel/bulut arasında yönlendirme kararı üretir."
    )
    parser.add_argument("--prompt", required=True, help="Yönlendirilecek kullanıcı isteği")
    parser.add_argument("--prefer", choices=PREFERENCES, default="balanced")
    parser.add_argument("--pretty", action="store_true", help="JSON çıktısını girintili yazdır")
    parser.add_argument(
        "--local-runtime-path",
        default="../local-runtime",
        help="ai-stack/local-runtime dizininin yolu (varsayılan: ../local-runtime)",
    )
    parser.add_argument(
        "--cloud-bridge-path",
        default="../cloud-bridge",
        help="ai-stack/cloud-bridge dizininin yolu (varsayılan: ../cloud-bridge)",
    )
    args = parser.parse_args()

    try:
        report = route_request(
            args.prompt,
            preference=args.prefer,
            local_runtime_cwd=args.local_runtime_path,
            cloud_bridge_cwd=args.cloud_bridge_path,
        )
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2 if args.pretty else None, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
