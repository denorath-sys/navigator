"""CLI: `python3 -m router --prompt "..." [--prefer balanced|privacy|cost|speed] [--pretty]`"""
import argparse
import json
import sys

from .decision import PREFERENCES
from .status import route_request


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Navigator OS router — produces a local/cloud routing decision for a request."
    )
    parser.add_argument("--prompt", required=True, help="The user request to route")
    parser.add_argument("--prefer", choices=PREFERENCES, default="balanced")
    parser.add_argument("--pretty", action="store_true", help="Print the JSON output indented")
    parser.add_argument(
        "--decide-only",
        action="store_true",
        help=(
            "Return only the routing decision (complexity/hardware_tier/"
            "model_ready/route/reasoning) and DO NOT RUN local-runtime or "
            "cloud-bridge (e.g. when ai-stack/assistant builds its own "
            "generation flow)"
        ),
    )
    parser.add_argument(
        "--local-runtime-path",
        default="../local-runtime",
        help="Path to the ai-stack/local-runtime directory (default: ../local-runtime)",
    )
    parser.add_argument(
        "--cloud-bridge-path",
        default="../cloud-bridge",
        help="Path to the ai-stack/cloud-bridge directory (default: ../cloud-bridge)",
    )
    args = parser.parse_args()

    try:
        report = route_request(
            args.prompt,
            preference=args.prefer,
            local_runtime_cwd=args.local_runtime_path,
            cloud_bridge_cwd=args.cloud_bridge_path,
            decide_only=args.decide_only,
        )
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2 if args.pretty else None, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
