"""CLI: `python3 -m assistant --prompt "..."` (tek seferlik, JSON çıktı) veya
`python3 -m assistant` (varsayılan: interaktif REPL, insan diliyle çıktı).
"""
import argparse
import json
import sys

from .conversation import AssistantError, run_turn
from .mcp_client import MCPClient, MCPClientError

SCHEMA_VERSION = "0.1"
PREFERENCES = ("balanced", "privacy", "cost", "speed")


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--prefer", choices=PREFERENCES, default="balanced")
    parser.add_argument("--router-path", default="../router")
    parser.add_argument("--local-runtime-path", default="../local-runtime")
    parser.add_argument("--cloud-bridge-path", default="../cloud-bridge")
    parser.add_argument("--mcp-tools-path", default="../mcp-tools")


def _run_turn_with_args(prompt: str, client: MCPClient, args) -> dict:
    return run_turn(
        prompt,
        client,
        preference=args.prefer,
        router_cwd=args.router_path,
        local_runtime_cwd=args.local_runtime_path,
        cloud_bridge_cwd=args.cloud_bridge_path,
    )


def _run_single_prompt(args) -> int:
    try:
        with MCPClient(cwd=args.mcp_tools_path) as client:
            result = _run_turn_with_args(args.prompt, client, args)
    except (AssistantError, MCPClientError) as e:
        print(
            json.dumps(
                {"schema_version": SCHEMA_VERSION, "status": "error", "error": str(e)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1

    report = {"schema_version": SCHEMA_VERSION, "status": "ok", **result}
    print(json.dumps(report, indent=2 if args.pretty else None, ensure_ascii=False))
    return 0


def _run_repl(args) -> int:
    print("Navigator Asistan — çıkmak için Ctrl+D veya 'çıkış' yaz.", file=sys.stderr)
    try:
        with MCPClient(cwd=args.mcp_tools_path) as client:
            while True:
                try:
                    prompt = input("> ").strip()
                except EOFError:
                    print(file=sys.stderr)
                    break
                if not prompt:
                    continue
                if prompt in ("çıkış", "exit", "quit"):
                    break
                try:
                    result = _run_turn_with_args(prompt, client, args)
                except AssistantError as e:
                    print(f"[hata] {e}")
                    continue
                print(result["content"])
                if result["tool_calls"]:
                    tool_names = ", ".join(t["name"] for t in result["tool_calls"])
                    print(f"  (kullanılan araçlar: {tool_names})", file=sys.stderr)
    except MCPClientError as e:
        print(f"mcp-tools'a bağlanılamadı: {e}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Navigator OS assistant — router/mcp-tools/cloud-bridge'i tek bir "
            "konuşma döngüsünde birleştirir."
        )
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Verilirse tek seferlik çalışır (JSON çıktı); yoksa interaktif REPL başlar",
    )
    parser.add_argument("--pretty", action="store_true", help="(--prompt ile) JSON çıktısını girintili yazdır")
    _add_common_args(parser)
    args = parser.parse_args()

    if args.prompt is not None:
        return _run_single_prompt(args)
    return _run_repl(args)


if __name__ == "__main__":
    sys.exit(main())
