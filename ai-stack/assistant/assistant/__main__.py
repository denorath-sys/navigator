"""CLI: `python3 -m assistant --prompt "..."` (one-shot, JSON output) or
`python3 -m assistant` (the default: an interactive REPL, human-readable output).

Conversation history:
- in the REPL it is kept in memory automatically (for the session), and
  cleared with `/reset`.
- if `--history-file <path>` is given, the history is kept persistently in a
  JSON file — in both one-shot and REPL mode, written to the file after every
  turn (so that a crash does not lose the history).
"""
import argparse
import json
import os
import sys

from .conversation import AssistantError, run_turn
from .mcp_client import MCPClient, MCPClientError

SCHEMA_VERSION = "0.1"
PREFERENCES = ("balanced", "privacy", "cost", "speed")
RESET_COMMANDS = ("/reset", "/yeni")
EXIT_COMMANDS = ("exit", "exit", "quit")


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--prefer", choices=PREFERENCES, default="balanced")
    parser.add_argument("--router-path", default="../router")
    parser.add_argument("--local-runtime-path", default="../local-runtime")
    parser.add_argument("--cloud-bridge-path", default="../cloud-bridge")
    parser.add_argument("--mcp-tools-path", default="../mcp-tools")
    parser.add_argument(
        "--history-file",
        default=None,
        help="Read/write the conversation history from/to this JSON file (not persisted if omitted)",
    )


def _load_history(args) -> list[dict]:
    if not args.history_file or not os.path.exists(args.history_file):
        return []
    with open(args.history_file, encoding="utf-8") as f:
        return json.load(f)


def _save_history(args, history: list[dict]) -> None:
    if not args.history_file:
        return
    with open(args.history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def _run_turn_with_args(prompt: str, client: MCPClient, args, history: list[dict]) -> dict:
    return run_turn(
        prompt,
        client,
        history=history,
        preference=args.prefer,
        router_cwd=args.router_path,
        local_runtime_cwd=args.local_runtime_path,
        cloud_bridge_cwd=args.cloud_bridge_path,
    )


def _run_single_prompt(args) -> int:
    history = _load_history(args)
    try:
        with MCPClient(cwd=args.mcp_tools_path) as client:
            result = _run_turn_with_args(args.prompt, client, args, history)
    except (AssistantError, MCPClientError) as e:
        print(
            json.dumps(
                {"schema_version": SCHEMA_VERSION, "status": "error", "error": str(e)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1

    _save_history(args, result["history"])
    report = {"schema_version": SCHEMA_VERSION, "status": "ok", **result}
    print(json.dumps(report, indent=2 if args.pretty else None, ensure_ascii=False))
    return 0


def _run_repl(args) -> int:
    print(
        "Navigator Assistant — press Ctrl+D or type 'exit' to quit, "
        "'/reset' to clear the history.",
        file=sys.stderr,
    )
    history = _load_history(args)
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
                if prompt in EXIT_COMMANDS:
                    break
                if prompt in RESET_COMMANDS:
                    history = []
                    _save_history(args, history)
                    print("(conversation history cleared)", file=sys.stderr)
                    continue
                try:
                    result = _run_turn_with_args(prompt, client, args, history)
                except AssistantError as e:
                    print(f"[hata] {e}")
                    continue
                history = result["history"]
                _save_history(args, history)
                print(result["content"])
                if result["tool_calls"]:
                    tool_names = ", ".join(t["name"] for t in result["tool_calls"])
                    print(f"  (tools used: {tool_names})", file=sys.stderr)
    except MCPClientError as e:
        print(f"Could not connect to mcp-tools: {e}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Navigator OS assistant — combines router/mcp-tools/cloud-bridge "
            "into a single conversation loop."
        )
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="If given, runs once (JSON output); otherwise an interactive REPL starts",
    )
    parser.add_argument("--pretty", action="store_true", help="(with --prompt) print the JSON output indented")
    _add_common_args(parser)
    args = parser.parse_args()

    if args.prompt is not None:
        return _run_single_prompt(args)
    return _run_repl(args)


if __name__ == "__main__":
    sys.exit(main())
