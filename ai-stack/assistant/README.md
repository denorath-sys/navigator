# ai-stack/assistant/

## What it does

The first concrete step towards Navigator's **Phase 4** goal, an
"end-to-end assistant panel experience": a CLI/REPL that combines `router`,
`mcp-tools`, `local-runtime` and `cloud-bridge` into a single real
conversation loop. This is the first real proof of the "everything should be
discoverable" design principle — instead of searching the web, the user can
ask something like "how many cores does this machine have?" directly and get
the right answer **from a real tool call** (see `docs/architecture.md`,
"Design principles").

Because the Quickshell/Hyprland UI could not be tested on this machine (see
`shell/README.md`, `ai-stack/mcp-tools/README.md`), Phase 4 began **without
waiting for the UI**, with a terminal experience that could genuinely be run
and tested on this machine.

## Architecture

```
user prompt
      │
      ▼
router --decide-only  ──►  hardware-probe (tier decision)
      │
      ├── route: "local" ──► local-runtime --converse (tool-use loop, RESTRICTED tool set)
      │
      └── route: "cloud" ──► cloud-bridge --converse (tool-use loop, FULL tool set)
                                    │         ▲
                                    ▼         │
                              mcp-tools (real tool call — MCP stdio)
```

Both the `local` and the `cloud` route build a REAL tool-use loop — both can
genuinely call the mcp-tools tools. The difference is which tools they can
reach and how reliable they are (see "Local tool-use" below).

- **`router --decide-only`**: a flag added to the router — it returns only
  the routing decision (`complexity`/`hardware_tier`/`model_ready`/`route`/
  `reasoning`) and DOES NOT RUN `local-runtime` or `cloud-bridge`. The
  reason: the assistant has to build its own generation flow (the tool-use
  loop), and having the router make its own one-shot call and then throwing
  the result away would be both wasteful and an unnecessary real API/model
  call.
- **`cloud_bridge --converse`**: a mode added to cloud-bridge's CLI — it
  takes a full message list plus a `tools` schema (Claude format) from
  stdin, and prints the RAW Claude API response (including `tool_use` blocks
  and `stop_reason`) to stdout.
- **`local_runtime --converse`**: a mode added to local-runtime's CLI — it
  takes a full message list plus a `tools` schema (OpenAI-like format) from
  stdin, and prints the RAW Ollama `/api/chat` response (including
  `tool_calls`) to stdout.
- **`mcp_client.py`**: a real MCP client against mcp-tools. Unlike the
  "one-shot subprocess" pattern of the other ai-stack modules
  (`python3 -m X --prompt ...`, reading the JSON once the process ends),
  there is a **persistent session** here — `initialize` happens once, and
  then multiple `tools/call` requests are sent over the same process (as the
  MCP protocol requires).
- **`conversation.py`**: `run_turn()` — dispatches to `run_cloud_turn()`
  (the Claude tool-use loop, full tool set) or `run_local_turn()` (the
  Ollama tool-use loop, restricted tool set) according to the router's
  decision.

## Conversation history / memory

Both paths use the same flat `history: [{"role", "content"}, ...]` format —
only user/assistant TEXT turns (neither Claude's tool_use/tool_result blocks
nor Ollama's tool_calls are included in the history; they stay within their
own turn). This keeps the history portable even if the route changes within
a conversation (local first, then cloud) — both map directly onto
Claude's/Ollama's native `{"role", "content"}` message format.

The history is trimmed at `MAX_HISTORY_MESSAGES` (20 messages, ~10 turns) —
preventing unbounded growth and a needlessly growing prompt/API cost.

**Where it is kept:**
- In the REPL, automatically in memory (for the session), cleared with
  `/reset`.
- If `--history-file <path>` is given, PERSISTENTLY in a JSON file — in both
  `--prompt` and REPL mode, written to the file after every turn (so a crash
  does not lose the history) — **memory even across separate processes**.

## `run_cloud_turn()` — a real tool-use loop (full tool set)

1. The schema of mcp-tools' 10 tools is fetched with
   `mcp_client.list_tools()` and converted to Claude's `tools` format
   (`inputSchema` → `input_schema`).
2. A message is sent to Claude. If the response has
   `stop_reason: "tool_use"`, every `tool_use` block is **genuinely**
   executed via `mcp_client.call_tool()` (not a mock — real `hardware_tier`,
   `read_file`, `list_windows` and so on, including `write_file` /
   `delete_file` / `rename_file`).
3. The result is fed back as a `tool_result` message and Claude is called
   again.
4. This repeats until Claude gives a `stop_reason` other than `tool_use` (at
   most 8 turns — infinite-loop protection), and the final text is returned.

A real example run (on this machine, with the real Claude API and real
mcp-tools). The transcript is kept verbatim as captured, which is why it is
in Turkish:

```
$ python3 -m assistant --prompt "Bu makinede kaç tane CPU çekirdeği var, toplam RAM ne kadar, ve ayrık bir grafik kartı var mı yok mu, ... gerçek donanım tespit aracını kullanarak öğren ..." --pretty
{
  "status": "ok",
  "content": "Donanım tespit aracının döndürdüğü gerçek verilere göre:\n\n- CPU çekirdeği: 6 fiziksel / 6 mantıksal (Intel i5-8500 @ 3.00GHz)\n- Toplam RAM: ~15.4 GB\n- Ayrık grafik kartı: Yok, yalnızca tümleşik Intel GPU var",
  "tool_calls": [{"name": "hardware_tier", "input": {}}],
  "route": "cloud",
  "hardware_tier": "low",
  "reasoning": "complex request + low hardware tier: the local model may be insufficient"
}
```

All the numbers are real and correct (they match this machine's real
hardware).

## `run_local_turn()` — local tool-use (restricted tool set, known reliability limitation)

It builds a tool-use loop in the same pattern via Ollama `/api/chat` — but
in real testing the behaviour of `llama3.2:3b` (3B parameters, far smaller
than Claude in the cloud) turned out to be **noticeably less reliable**.
This is not a code bug but a known, documented limitation of small models —
and per the principle "nothing that isn't real is presented as successful"
it is honestly recorded here:

### Problems actually observed, and the real fixes

1. **Hallucinated arguments.** It produced made-up arguments such as
   `{"path": "/home/chief"}` or `{"": "null"}` even for the zero-parameter
   `hardware_tier` tool. **Fix:** the arguments of every tool call are
   filtered against the `properties` keys of the tool's real `inputSchema` —
   any key not in the schema is dropped.

2. **A security risk — a hallucinated write call.** Even on a harmless
   "just say 'hello'" request, it spontaneously tried to call `write_file`
   with `overwrite: true` (it failed with an error at the mcp-tools layer
   because the target `/home/chief` is a directory — but on another path it
   really could have modified a file). This was a genuine risk of violating
   the principle "every system-modifying action requires explicit
   confirmation". **Fix:** `write_file`/`delete_file`/`rename_file` are NOT
   shown to the local model at all (`LOCAL_SAFE_TOOL_NAMES` — read-only
   tools only: `hardware_tier`, `route_request`, `read_file`,
   `list_directory`, `list_windows`, `list_workspaces`, `active_window`). If
   the model nonetheless hallucinates a call to a tool it was not shown, the
   defence layer rejects it before it ever reaches
   `mcp_client.call_tool()` — real testing verified both "never shown" and
   "rejected even if not shown".

3. **Instability with memory and tool-use together.** Without a system
   prompt, the model tried to make unnecessary tool calls even on a simple
   memory question ("What was my name?"), and sometimes wrote raw JSON text
   as a plain answer instead of structured `tool_calls`. **Fix:** the same
   `SYSTEM_PROMPT` as cloud is now given to local as well, with an added
   instruction not to use tools when something from the earlier conversation
   is being asked — in real testing this markedly increased reliability but
   **did not eliminate the problem** (see below).

### The remaining, accepted real limitation

Even after the fixes above, the 3B model can occasionally (i) call a
read-only tool unnecessarily (harmless, but pointless), or (ii) produce
tool-call-shaped raw JSON text instead of structured `tool_calls` (in which
case no tool runs at all for that turn, and the model writes text that looks
like an "answer" but is useless). This is **the model's own inherent
variability** — it was not observed on 8B+ models or in the cloud (Claude).
The real test suite therefore retries a limited number of times in scenarios
that depend on content quality (see `tests/test_integration.py`,
`_run_cli_until`) — the security tests (the write tool is never shown or
executed) do not use this, since they remain DETERMINISTIC.

A real, successful example run (after the fixes, on this machine), kept
verbatim:

```
$ python3 -m assistant --prompt "Bu makinede kaç CPU çekirdeği var? Aracı kullanarak öğren, kısa cevap ver."
{"content": "Bu makinenin 6 CPU çekirdeği vardır.", "tool_calls": [{"name": "hardware_tier", "input": {}}], "route": "local", ...}
```

This is exactly the scenario that failed in the first implementation
(BEFORE the fixes), where it produced an irrelevant hallucination such as
`"Lütfen makine modelini veya aracinızı girin..."` — it now answers with
real, correct data.

## Usage

No external dependencies, only Python 3.11+ (stdlib). It must sit next to
`router`, `mcp-tools`, `local-runtime` and `cloud-bridge` (as sibling
directories).

One-shot (JSON output, for tests/scripting):

```sh
cd ai-stack/assistant
python3 -m assistant --prompt "..." [--prefer balanced|privacy|cost|speed] [--pretty]
```

Interactive REPL (the default, human-readable output, history automatically
in memory):

```sh
cd ai-stack/assistant
python3 -m assistant
> How many cores does this machine have?
...
> /reset   # clears the conversation history
> exit
```

Persistent history (remembers across separate runs/processes too):

```sh
python3 -m assistant --prompt "..." --history-file ~/.navigator-assistant-history.json
```

The cloud path needs a real Claude API key — see
`ai-stack/cloud-bridge/README.md`, "Wiring up the credential locally". The
local path (Ollama) always works and needs no credentials.

Tests:

```sh
cd ai-stack/assistant
python3 -m unittest discover -v -s tests
```

## Out of scope — not done yet

- The local path's reliability is not complete (see above) — that is a
  limitation stemming from model size, and may require a larger local model
  or a solution beyond prompt engineering.
- It is not connected to a real Quickshell/Hyprland UI — that depends on the
  deferred real compositor test (see `ai-stack/mcp-tools/README.md`).
- No streaming — every response is returned in full, in one go.

**Completed in Phase 4 (previously out of scope here):** the router's
complexity heuristic now also uses the "might this need tools?" signal
(`mentions_tool_keywords()`, see `ai-stack/router/README.md`) — short
requests relating to hardware, files or windows now automatically fall
through to the cloud on a low tier, rather than only word count being
considered.

## Status

Phase 4 — `router` (`--decide-only`), `cloud-bridge` (`--converse`,
`send_messages()`), `local-runtime` (`--converse`, `chat()`) and the new
`assistant` module (`mcp_client.py`, `conversation.py`, CLI/REPL) are
complete. **Both the cloud and the local path now work with a real tool-use
loop** — cloud with the full tool set and reliably, local with a restricted
(read-only) tool set and with a reliability limitation documented from real
testing (see above). Conversation history/memory was added — in memory in
the REPL, and persistent even across separate processes via
`--history-file`. Verified end to end for real: with the real Claude API,
real Ollama and real mcp-tools, both genuinely calling tools, and both
honestly documented (in particular a security risk caught on the local path
in real testing — a hallucinated `write_file` call — which was genuinely
fixed by restricting tool access).

40 tests pass (27 mocked conversation tests, 7 mocked MCP client tests, and
6 real integration tests — four of which always run [local tool-use,
security, memory], and two of which run against the real Claude API when
credentials are present and are otherwise skipped automatically).
