"""CLI: `python3 -m cloud_bridge [--pretty]` (durum),
`python3 -m cloud_bridge --prompt "..." [--system ...] [--max-tokens N]` (tek turlu
a simplified report) or
`echo '{"messages": [...], "tools": [...]}' | python3 -m cloud_bridge --converse`
(multi-turn, the RAW API response — for callers building a tool-use loop, see
ai-stack/assistant).
"""
import argparse
import json
import sys

from .client import DEFAULT_MODEL, AnthropicClient, AnthropicError
from .status import SCHEMA_VERSION, build_status_report


def _extract_text(response: dict) -> str:
    return "".join(
        block.get("text", "")
        for block in response.get("content", [])
        if block.get("type") == "text"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Navigator OS cloud-bridge — Anthropic Claude API status or request."
    )
    parser.add_argument("--pretty", action="store_true", help="Print the JSON output indented")
    parser.add_argument(
        "--prompt",
        default=None,
        help="If given, sends a real Claude API request (otherwise only the credential status is reported)",
    )
    parser.add_argument("--system", default=None, help="System prompt (optional)")
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument(
        "--converse",
        action="store_true",
        help=(
            'Read {"messages": [...], "system": ..., "tools": [...], '
            '"model": ..., "max_tokens": ...} JSON from stdin, send it to the '
            "Claude API, and print the RAW response (including tool_use blocks "
            "and stop_reason) as JSON to stdout."
        ),
    )
    args = parser.parse_args()
    indent = 2 if args.pretty else None

    if args.converse:
        payload = json.load(sys.stdin)
        client = AnthropicClient()
        resolution = client.resolve_credentials()
        if not resolution.values:
            print(
                json.dumps(
                    {"status": "unavailable", "reason": resolution.unavailable_reason},
                    ensure_ascii=False,
                )
            )
            return 0
        try:
            response = client.send_messages(
                payload["messages"],
                model=payload.get("model", DEFAULT_MODEL),
                max_tokens=payload.get("max_tokens", 1024),
                system=payload.get("system"),
                tools=payload.get("tools"),
            )
        except AnthropicError as e:
            print(json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False), file=sys.stderr)
            return 1
        print(json.dumps(response, ensure_ascii=False))
        return 0

    if args.prompt is None:
        report = build_status_report()
        print(json.dumps(report, indent=indent, ensure_ascii=False))
        return 0

    client = AnthropicClient()
    report = {
        "schema_version": SCHEMA_VERSION,
        "provider": "anthropic",
        "model": DEFAULT_MODEL,
        "prompt_preview": args.prompt[:80],
    }

    resolution = client.resolve_credentials()
    if not resolution.values:
        report["status"] = "unavailable"
        # Not merely "not configured": the file may also have been REFUSED
        # because of wrong permissions. This string is shown to the user in
        # AssistantPanel, so being distinguishing makes a real difference.
        report["reason"] = resolution.unavailable_reason
        print(json.dumps(report, indent=indent, ensure_ascii=False))
        return 0

    try:
        response = client.generate(args.prompt, max_tokens=args.max_tokens, system=args.system)
    except AnthropicError as e:
        report["status"] = "error"
        report["error"] = str(e)
        print(json.dumps(report, indent=indent, ensure_ascii=False), file=sys.stderr)
        return 1

    report["status"] = "ok"
    report["content"] = _extract_text(response)
    print(json.dumps(report, indent=indent, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
