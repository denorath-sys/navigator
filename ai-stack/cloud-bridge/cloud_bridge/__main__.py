"""CLI: `python3 -m cloud_bridge [--pretty]` (durum),
`python3 -m cloud_bridge --prompt "..." [--system ...] [--max-tokens N]` (tek turlu
basitleştirilmiş rapor) veya
`echo '{"messages": [...], "tools": [...]}' | python3 -m cloud_bridge --converse`
(çok turlu, HAM API yanıtı — tool-use döngüsü kuran çağıranlar için, bkz.
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
        description="Navigator OS cloud-bridge — Anthropic Claude API durumu veya isteği."
    )
    parser.add_argument("--pretty", action="store_true", help="JSON çıktısını girintili yazdır")
    parser.add_argument(
        "--prompt",
        default=None,
        help="Verilirse gerçek bir Claude API isteği gönderir (yoksa sadece kimlik bilgisi durumu raporlanır)",
    )
    parser.add_argument("--system", default=None, help="Sistem promptu (isteğe bağlı)")
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument(
        "--converse",
        action="store_true",
        help=(
            'stdin\'den {"messages": [...], "system": ..., "tools": [...], '
            '"model": ..., "max_tokens": ...} JSON\'u okur, Claude API\'ye '
            "gönderir, HAM yanıtı (tool_use blokları/stop_reason dahil) stdout'a "
            "JSON basar."
        ),
    )
    args = parser.parse_args()
    indent = 2 if args.pretty else None

    if args.converse:
        payload = json.load(sys.stdin)
        client = AnthropicClient()
        if not client.is_available():
            print(
                json.dumps(
                    {"status": "unavailable", "reason": "credentials_not_configured"},
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

    if not client.is_available():
        report["status"] = "unavailable"
        report["reason"] = "credentials_not_configured"
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
