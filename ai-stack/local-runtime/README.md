# ai-stack/local-runtime/

## What it does

Runs a local LLM on the device, matching the tier determined by
`hardware-probe/`. **Architectural decision (Phase 2):
[Ollama](https://ollama.com)** — preferred over llama.cpp because it
provides a clean REST API (`localhost:11434`) and model pulling/management
by name; it is enough for `router/` to speak to a single HTTP client, and no
separate model file or quantization management is needed. The goal is for
basic assistant functionality to work without an internet connection.

**It is now fully working on this machine**: Ollama installed +
`llama3.2:3b` pulled → `model_ready: true` → real local generation is
possible.

**`router` integration (Phase 2):** when the `route: "local"` decision is
made, `router/local.py` invokes this module as a subprocess with the
`--prompt` flag — see `ai-stack/router/README.md`, "local-runtime
integration".

**`assistant` integration (Phase 4):** `chat()`/`--converse` were added — it
sends multi-turn, tool-calling-capable requests via Ollama's `/api/chat`
endpoint (OpenAI-like `tool_calls`). `ai-stack/assistant` uses this to build
a real tool-use loop — see `ai-stack/assistant/README.md`, "Local tool-use".

## Usage

No external dependencies, only Python 3.11+ (stdlib). It must sit next to
`hardware-probe` (as a sibling directory).

```sh
cd ai-stack/local-runtime
python3 -m local_runtime --pretty                      # status only
python3 -m local_runtime --prompt "hello" --pretty     # real request (with the recommended model)
```

**`--converse`** (added in Phase 4 for `ai-stack/assistant`): reads a full
message list plus an optional `tools` schema from stdin (in the OpenAI-like
`{"type": "function", "function": {...}}` format) and prints the RAW
`/api/chat` response from Ollama (including `tool_calls`) to stdout:

```sh
echo '{"messages": [{"role": "user", "content": "hello"}], "tools": [...]}' \
  | python3 -m local_runtime --converse
```

Tests:

```sh
cd ai-stack/local-runtime
python3 -m unittest discover -v -s tests
```

## Example output

On this machine (Ollama installed and running, `llama3.2:3b` pulled —
`hardware-probe` detected tier="low"):

```json
{
  "schema_version": "0.1",
  "hardware_tier": "low",
  "recommended_model": {"model": "llama3.2:3b", "approx_size_gb": 2.0},
  "ollama_available": true,
  "installed_models": ["llama3.2:3b"],
  "model_ready": true
}
```

With `--prompt` — **a real local generation** (tested on this machine). The
prompt and the reply are kept verbatim as they were captured, which is why
they are in Turkish:

```json
{
  "schema_version": "0.1",
  "provider": "ollama",
  "hardware_tier": "low",
  "prompt_preview": "Merhaba, sen kimsin?",
  "model": "llama3.2:3b",
  "status": "ok",
  "content": "Merhaba! Ben bir model conversasyon otomatuım. Ne gibi yardımcı olabilirim?"
}
```

When the model is not installed or Ollama is down, it returns
`status: "unavailable"` and one of these three `reason` values:
`no_local_model_recommended` (tier "minimal"), `ollama_not_running` (Ollama
is down), `model_not_installed` (Ollama is up but the model has not been
pulled).

## Tier → model mapping (draft, `local_runtime/models.py`)

| Tier | Recommended model | Approx. size |
|---|---|---|
| `minimal` | *(none — should be routed to cloud-bridge)* | — |
| `low` | `llama3.2:3b` | ~2 GB |
| `mid` | `llama3.1:8b` | ~4.7 GB |
| `high` | `llama3.1:70b` | ~40 GB |

This mapping is a draft and will be revised in Phase 3+ as real usage and
benchmark data accumulate. Only the `low` tier's model (`llama3.2:3b`) was
pulled on this machine — `mid`/`high` do not apply to this hardware at all.

## The download is done (with the owner's approval, in two separate steps)

1. **Ollama itself**: `curl -fsSL https://ollama.com/install.sh | sh`
   (~1.37 GB, the official install script, as a systemd service via sudo).
   Since this machine has no discrete GPU, it was installed in CPU-only mode.
2. **The model weights**: `ollama pull llama3.2:3b` (~2 GB).

Both were done with separate, explicit approvals (a project constraint:
downloads over 200 MB are not started without approval).

## Known limitation — timeouts

The default timeout of `OllamaClient.generate()` is 300 seconds — far higher
than for lightweight metadata calls such as `is_available()`/`list_models()`,
because on the first call the model has to be loaded into memory and
inference on CPU can take minutes (this bug was caught and fixed on the real
machine: the first attempt returned `"error": "timed out"` with the default
5-second timeout).

## Status

Phase 2 — the orchestration/client layer, the `router` integration, and
**the real Ollama installation AND the real model download** are complete
(`models.py`, `client.py`, `status.py`, and the
`python3 -m local_runtime [--prompt ...]` CLI). `chat()`/`--converse` were
added in Phase 4 — real testing verified `llama3.2:3b`'s tool-calling (via
Ollama `/api/chat`): the model genuinely produced a structured `tool_calls`
block (`{"name": "hardware_tier", "arguments": {}}`). 20 tests pass — two of
them real calls (`generate()` and tool-calling via `chat()`, with the model
loaded into memory and really running). `route: "local"` now genuinely works
end to end on this machine, for both plain generation and tool-use (for
tool-use quality and reliability see `ai-stack/assistant/README.md`, "Local
tool-use — known reliability limitation").
