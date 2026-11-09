"""CLI: `python3 -m assistant --prompt "..."` (one-shot, JSON output) or
`python3 -m assistant` (the default: an interactive REPL, human-readable output).

Conversation history:
- in the REPL it is kept in memory automatically (for the session), and
  cleared with `/reset`.
- if `--history-file <path>` is given, the history is kept persistently in a
  JSON file — in both one-shot and REPL mode, written to the file after every
  turn (so that a crash does not lose the history).
- `--default-history` is the same, at the per-user default path
  (`$XDG_STATE_HOME/navigator/assistant-history.json`, falling back to
  `~/.local/state/...`). This is what the shell panel uses: the path is
  resolved HERE rather than in QML for the same reason cloud-bridge resolves
  its credential file at the end of the chain — the panel's environment is
  whatever the compositor was started with, and the panel should not have to
  know where state lives.
- `--reset` clears the history file and exits (the panel's `/reset`).

The history file is written 0600 inside a 0700 directory, atomically: it holds
everything the user has said to the assistant, which is no less private than
the credential file next door.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .conversation import AssistantError, run_turn
from .mcp_client import MCPClient, MCPClientError

SCHEMA_VERSION = "0.1"
PREFERENCES = ("balanced", "privacy", "cost", "speed")
RESET_COMMANDS = ("/reset", "/yeni")
EXIT_COMMANDS = ("exit", "quit")

HISTORY_RELATIVE_PATH = Path("navigator") / "assistant-history.json"
REASON_HISTORY_MALFORMED = "history_file_malformed"
REASON_SUBPROCESS_FAILED = "subprocess_failed"


class HistoryFileError(Exception):
    """The history file exists but is not a JSON list of messages."""


def default_history_path(environ=os.environ) -> Path:
    """`$XDG_STATE_HOME/navigator/assistant-history.json`, otherwise
    `~/.local/state/navigator/assistant-history.json`.

    As in cloud_bridge/config.py: per the XDG Base Directory spec a value that
    is unset, empty or not absolute is ignored."""
    xdg = environ.get("XDG_STATE_HOME", "")
    if xdg.startswith("/"):
        base = Path(xdg)
    else:
        base = Path(environ.get("HOME", "~")).expanduser() / ".local" / "state"
    return base / HISTORY_RELATIVE_PATH


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--prefer", choices=PREFERENCES, default="balanced")
    parser.add_argument("--router-path", default="../router")
    parser.add_argument("--local-runtime-path", default="../local-runtime")
    parser.add_argument("--cloud-bridge-path", default="../cloud-bridge")
    parser.add_argument("--mcp-tools-path", default="../mcp-tools")
    history = parser.add_mutually_exclusive_group()
    history.add_argument(
        "--history-file",
        default=None,
        help="Read/write the conversation history from/to this JSON file (not persisted if omitted)",
    )
    history.add_argument(
        "--default-history",
        action="store_true",
        help="Like --history-file, at $XDG_STATE_HOME/navigator/assistant-history.json",
    )


def _resolve_history_file(args) -> None:
    if args.default_history:
        args.history_file = str(default_history_path())


def _load_history(args) -> list[dict]:
    if not args.history_file or not os.path.exists(args.history_file):
        return []
    try:
        with open(args.history_file, encoding="utf-8") as f:
            history = json.load(f)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HistoryFileError(f"{args.history_file}: {e}") from e
    if not isinstance(history, list) or not all(
        isinstance(m, dict) and isinstance(m.get("role"), str) and "content" in m for m in history
    ):
        raise HistoryFileError(f"{args.history_file}: not a list of {{role, content}} messages")
    return history


def _save_history(args, history: list[dict]) -> None:
    if not args.history_file:
        return
    path = Path(args.history_file)
    # mkdir's mode only applies to directories it creates; an existing
    # ~/.local/state is left as the user has it.
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Atomic: the panel and a REPL may both use the default file, and a crash
    # half-way through a write must not leave a file that _load_history then
    # refuses forever. mkstemp creates the file 0600.
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _print_error(error: str, reason: str | None = None) -> None:
    report = {"schema_version": SCHEMA_VERSION, "status": "error", "error": error}
    if reason:
        report["reason"] = reason
    print(json.dumps(report, ensure_ascii=False), file=sys.stderr)


def _run_reset(args) -> int:
    if not args.history_file:
        _print_error("--reset needs --history-file or --default-history")
        return 2
    # Deliberately does NOT read the file first: --reset is also the way out
    # of a malformed history file, so it must not fail on one.
    _save_history(args, [])
    print(json.dumps({"schema_version": SCHEMA_VERSION, "status": "ok", "reset": True}))
    return 0


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
    try:
        history = _load_history(args)
    except HistoryFileError as e:
        _print_error(str(e), REASON_HISTORY_MALFORMED)
        return 1
    try:
        with MCPClient(cwd=args.mcp_tools_path) as client:
            result = _run_turn_with_args(args.prompt, client, args, history)
    except AssistantError as e:
        _print_error(str(e), e.reason)
        return 1
    except MCPClientError as e:
        _print_error(str(e))
        return 1
    except subprocess.CalledProcessError as e:
        # router / cloud-bridge / local-runtime exited non-zero. Without this
        # the caller (the panel) got a bare traceback; the module's own stderr
        # is the useful part, so it is kept, trimmed.
        detail = (e.stderr or "").strip()[-500:]
        _print_error(
            f"{' '.join(map(str, e.cmd))} exited {e.returncode}: {detail or '(no stderr)'}",
            REASON_SUBPROCESS_FAILED,
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
    try:
        history = _load_history(args)
    except HistoryFileError as e:
        print(f"Could not read the history file ({e}) — run with --reset to clear it.", file=sys.stderr)
        return 1
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
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear the history file (--history-file / --default-history) and exit",
    )
    _add_common_args(parser)
    args = parser.parse_args()
    _resolve_history_file(args)

    if args.reset:
        return _run_reset(args)
    if args.prompt is not None:
        return _run_single_prompt(args)
    return _run_repl(args)


if __name__ == "__main__":
    sys.exit(main())
