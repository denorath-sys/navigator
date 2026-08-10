"""The assistant's conversation orchestration.

The routing decision is taken with `router --decide-only` (without running
local-runtime/cloud-bridge POINTLESSLY — see "decide_only" in
router/status.py), and then both the **cloud** and the **local** route build a
REAL tool-use loop: mcp-tools' `tools/list` output is converted to the
relevant provider's tool format; every time the model returns a tool call the
corresponding mcp-tools tool is GENUINELY executed (see mcp_client.py) and the
result is fed back — repeating until the model gives a final text response.

- **cloud**: the Claude Messages API (`tool_use`/`tool_result` blocks). It has
  access to the full tool set.
- **local**: Ollama `/api/chat` (OpenAI-like `tool_calls` — verified on the
  real machine with `llama3.2:3b`, see local-runtime/README.md). It has access
  to READ-ONLY tools only (`LOCAL_SAFE_TOOL_NAMES`) — in real testing the 3B
  model spontaneously tried to call `write_file` with `overwrite=true` even on
  a harmless request such as "just say 'hello'" (it only failed at the
  mcp-tools layer because the target happened to be a directory; on another
  path it really could have modified a file). Since that was a genuine risk of
  violating the "every system-modifying action requires explicit confirmation"
  principle, the write/delete/rename tools are NOT shown to the local model at
  all — cloud (Claude) is far more reliable and keeps full access.

**Conversation history:** both use the same flat
`history: [{"role", "content"}, ...]` format (user/assistant TEXT turns only —
neither Claude's tool_use/tool_result blocks nor Ollama's tool_calls are
INCLUDED in the history, they stay within their own turn). This keeps the
history portable even if the route changes within a conversation (e.g. local
first, then cloud).
"""
import json
import subprocess

from .mcp_client import MCPClient

ROUTER_CMD = ["python3", "-m", "router"]
LOCAL_RUNTIME_CMD = ["python3", "-m", "local_runtime"]
CLOUD_BRIDGE_CMD = ["python3", "-m", "cloud_bridge"]

# The prompt is English, but it deliberately does NOT pin the answer to
# English: Navigator's own author writes in Turkish, and an assistant that
# replies in a language the user did not use is a worse assistant. Answering
# in the user's language is therefore an explicit instruction rather than a
# side effect of the prompt's language.
SYSTEM_PROMPT = (
    "You are Navigator OS's assistant, embedded in the operating system. "
    "Answer the user's questions about the SYSTEM/HARDWARE with real data, "
    "using the tools you are given — never guess or make anything up. But if "
    "the user is asking about something they said earlier in the conversation "
    "(a name, a preference and so on) DO NOT USE A TOOL — answer directly "
    "from the conversation history. Always reply in the same language the "
    "user wrote in. Be short and clear."
)
MAX_TOOL_ITERATIONS = 8
MAX_HISTORY_MESSAGES = 20  # ~10 user/assistant turns — prevents unbounded growth

# Only read-only tools are shown to the local (small, less reliable) model —
# see the run_local_turn() docstring and the hallucinated write_file call
# caught in real testing.
LOCAL_SAFE_TOOL_NAMES = frozenset(
    {
        "hardware_tier",
        "route_request",
        "read_file",
        "list_directory",
        "list_windows",
        "list_workspaces",
        "active_window",
    }
)


class AssistantError(Exception):
    """Raised when an unrecoverable error occurs during the conversation loop."""


def decide_route(
    prompt: str, preference: str = "balanced", router_cwd: str = "../router"
) -> dict:
    result = subprocess.run(
        ROUTER_CMD + ["--prompt", prompt, "--prefer", preference, "--decide-only"],
        cwd=router_cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _mcp_tools_to_claude_tools(mcp_tools: list[dict]) -> list[dict]:
    return [
        {"name": t["name"], "description": t["description"], "input_schema": t["inputSchema"]}
        for t in mcp_tools
    ]


def _mcp_tools_to_ollama_tools(mcp_tools: list[dict]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["inputSchema"],
            },
        }
        for t in mcp_tools
    ]


def _extract_text(content_blocks: list[dict]) -> str:
    return "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")


def _call_cloud_bridge_converse(payload: dict, cwd: str = "../cloud-bridge") -> dict:
    result = subprocess.run(
        CLOUD_BRIDGE_CMD + ["--converse"],
        cwd=cwd,
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _call_local_runtime_converse(payload: dict, cwd: str = "../local-runtime") -> dict:
    result = subprocess.run(
        LOCAL_RUNTIME_CMD + ["--converse"],
        cwd=cwd,
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def run_cloud_turn(
    prompt: str,
    mcp_client: MCPClient,
    history: list[dict] | None = None,
    cloud_bridge_cwd: str = "../cloud-bridge",
    max_tokens: int = 1024,
    max_iterations: int = MAX_TOOL_ITERATIONS,
) -> dict:
    """Run a real tool-use loop with Claude. The returned dict:
    `{"content": str, "tool_calls": [...], "route": "cloud", "history": [...]}`.

    `history` (if given) is prepended to Claude's message list — Claude sees
    the earlier turns. The returned `history` appends this turn's plain-text
    summary (WITHOUT tool_use/tool_result) to the previous history.
    """
    tools = _mcp_tools_to_claude_tools(mcp_client.list_tools())
    messages: list[dict] = list(history or []) + [{"role": "user", "content": prompt}]
    tool_calls: list[dict] = []

    for _ in range(max_iterations):
        response = _call_cloud_bridge_converse(
            {
                "messages": messages,
                "system": SYSTEM_PROMPT,
                "tools": tools,
                "max_tokens": max_tokens,
            },
            cwd=cloud_bridge_cwd,
        )

        if response.get("status") == "unavailable":
            raise AssistantError(f"cloud-bridge unavailable: {response.get('reason')}")
        if response.get("status") == "error":
            raise AssistantError(f"Claude API returned an error: {response.get('error')}")

        messages.append({"role": "assistant", "content": response["content"]})

        if response.get("stop_reason") != "tool_use":
            final_text = _extract_text(response["content"])
            return {
                "content": final_text,
                "tool_calls": tool_calls,
                "route": "cloud",
                "history": (history or [])
                + [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": final_text},
                ],
            }

        tool_results = []
        for block in response["content"]:
            if block.get("type") != "tool_use":
                continue
            tool_calls.append({"name": block["name"], "input": block["input"]})
            try:
                result = mcp_client.call_tool(block["name"], block["input"])
                result_text = _extract_text(result["content"])
                is_error = bool(result.get("isError", False))
            except Exception as e:
                result_text = f"Tool call failed: {e}"
                is_error = True
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": result_text,
                    "is_error": is_error,
                }
            )
        messages.append({"role": "user", "content": tool_results})

    raise AssistantError(
        f"Claude is still calling tools after {max_iterations} turns "
        "(infinite-loop protection)"
    )


def run_local_turn(
    prompt: str,
    mcp_client: MCPClient,
    history: list[dict] | None = None,
    local_runtime_cwd: str = "../local-runtime",
    max_iterations: int = MAX_TOOL_ITERATIONS,
) -> dict:
    """Run a real tool-use loop with Ollama (`/api/chat`) — the same pattern
    as `run_cloud_turn()`, only the tool format differs (Ollama uses
    OpenAI-like `tool_calls`, unlike Claude's `tool_use` blocks). The returned
    dict: `{"content": str, "tool_calls": [...],
    "route": "local", "history": [...]}`.
    """
    safe_tools_list = [t for t in mcp_client.list_tools() if t["name"] in LOCAL_SAFE_TOOL_NAMES]
    tools = _mcp_tools_to_ollama_tools(safe_tools_list)
    schemas_by_name = {t["name"]: t["inputSchema"] for t in safe_tools_list}
    # Without a system prompt (observed in real testing) the 3B model tries to
    # make unnecessary tool calls even on simple memory/chat questions — the
    # same SYSTEM_PROMPT is given here too, for consistency with the cloud path.
    messages: list[dict] = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + list(history or [])
        + [{"role": "user", "content": prompt}]
    )
    tool_calls: list[dict] = []

    for _ in range(max_iterations):
        response = _call_local_runtime_converse(
            {"messages": messages, "tools": tools}, cwd=local_runtime_cwd
        )

        if response.get("status") == "unavailable":
            raise AssistantError(f"local-runtime unavailable: {response.get('reason')}")
        if response.get("status") == "error":
            raise AssistantError(f"Ollama returned an error: {response.get('error')}")

        message = response["message"]
        messages.append(message)

        ollama_tool_calls = message.get("tool_calls") or []
        if not ollama_tool_calls:
            final_text = message.get("content", "")
            return {
                "content": final_text,
                "tool_calls": tool_calls,
                "route": "local",
                "history": (history or [])
                + [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": final_text},
                ],
            }

        for call in ollama_tool_calls:
            fn = call["function"]
            if fn["name"] not in schemas_by_name:
                # The model hallucinated a call to a tool it was not shown
                # (e.g. write_file) — the defence layer rejects it before it
                # ever reaches mcp_client.call_tool().
                tool_calls.append({"name": fn["name"], "input": fn.get("arguments") or {}})
                messages.append(
                    {
                        "role": "tool",
                        "content": f"Tool call rejected: '{fn['name']}' is not available to the local model.",
                    }
                )
                continue
            # In real testing llama3.2:3b made up hallucinated arguments even
            # for zero-parameter tools (e.g. {"path": "..."}, {"": "null"}) —
            # dropping keys that are not in the tool's inputSchema genuinely
            # prevents this class of error.
            schema = schemas_by_name[fn["name"]]
            allowed = set(schema.get("properties", {}).keys())
            args = {k: v for k, v in (fn.get("arguments") or {}).items() if k in allowed}
            tool_calls.append({"name": fn["name"], "input": args})
            try:
                result = mcp_client.call_tool(fn["name"], args)
                result_text = _extract_text(result["content"])
            except Exception as e:
                result_text = f"Tool call failed: {e}"
            # Ollama/llama3.2 does not require tool_call_id matching (verified
            # on the real machine) — role:"tool" + content is enough.
            messages.append({"role": "tool", "content": result_text})

    raise AssistantError(
        f"The model is still calling tools after {max_iterations} turns "
        "(infinite-loop protection)"
    )


def run_turn(
    prompt: str,
    mcp_client: MCPClient,
    history: list[dict] | None = None,
    preference: str = "balanced",
    router_cwd: str = "../router",
    local_runtime_cwd: str = "../local-runtime",
    cloud_bridge_cwd: str = "../cloud-bridge",
    max_tokens: int = 1024,
) -> dict:
    """Handle a single user request end to end: the router decision ->
    (cloud or local, both a real tool-use loop). If `history` is given (and
    trimmed to `MAX_HISTORY_MESSAGES`) it is used as context on both paths;
    the `history` in the returned dict can be passed straight into the next
    `run_turn()` call."""
    decision = decide_route(prompt, preference=preference, router_cwd=router_cwd)
    trimmed_history = (history or [])[-MAX_HISTORY_MESSAGES:]

    if decision["route"] == "cloud":
        result = run_cloud_turn(
            prompt,
            mcp_client,
            history=trimmed_history,
            cloud_bridge_cwd=cloud_bridge_cwd,
            max_tokens=max_tokens,
        )
    else:
        result = run_local_turn(
            prompt, mcp_client, history=trimmed_history, local_runtime_cwd=local_runtime_cwd
        )

    result["hardware_tier"] = decision["hardware_tier"]
    result["reasoning"] = decision["reasoning"]
    return result
