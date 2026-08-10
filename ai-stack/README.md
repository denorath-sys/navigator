# ai-stack/

The layer that makes Navigator "AI-native". It aims to present AI as a
natural part of the operating system rather than as a third-party
application.

It consists of six components, each detailed in its own README:

| Module | Responsibility |
|---|---|
| [`hardware-probe/`](hardware-probe/README.md) | Detects the hardware and determines the model tier — **verified on real hardware** |
| [`local-runtime/`](local-runtime/README.md) | Running local models (Ollama) — **works end to end**, tool-calling supported (Ollama + `llama3.2:3b` installed) |
| [`mcp-tools/`](mcp-tools/README.md) | MCP-based system/tool access — **10 tools, two transports (stdio + HTTP+SSE), really tested** |
| [`router/`](router/README.md) | Hybrid local↔cloud request routing — **both paths are real end to end** |
| [`cloud-bridge/`](cloud-bridge/README.md) | Cloud model provider (Anthropic Claude API) — **real credentials wired up, tool-use supported** |
| [`assistant/`](assistant/README.md) | Phase 4: a CLI/REPL combining the five above into a single real conversation loop — **a real tool-use loop on both cloud and local, plus persistent conversation history** |

## Data flow (real code — not just intent)

```
user prompt (assistant/ CLI or REPL)
        │
        ▼
router --decide-only  ──►  hardware-probe/ (tier decision)
        │
        ├── route: "local" ──► local-runtime/ --converse (tool-use, RESTRICTED tool set)
        │
        └── route: "cloud" ──► cloud-bridge/ --converse (tool-use, FULL tool set)
                                      │            ▲
                                      ▼            │
                                mcp-tools/ (real tool call — MCP stdio)
```

`shell/` (the Quickshell UI) was genuinely connected to this chain in
Phase 4: `shell/AssistantPanel.qml` invokes `router` as a subprocess, and
this was verified end to end in a real CI VM (see `shell/README.md`).

## Installation path in the image

**Layer 5** of `image/Containerfile` genuinely layers these six modules into
the Navigator image:

```
/usr/share/navigator/ai-stack/
├── hardware-probe/{hardware_probe/,pyproject.toml}
├── local-runtime/{local_runtime/,pyproject.toml}
├── cloud-bridge/{cloud_bridge/,pyproject.toml}
├── mcp-tools/{mcp_tools/,pyproject.toml}
├── router/{router/,pyproject.toml}
└── assistant/{assistant/,pyproject.toml}
```

**The flat sibling hierarchy is a runtime contract, not a preference.**
The modules invoke each other as `python3 -m <module>` subprocesses using
sibling paths relative to the cwd (`router` → `../local-runtime`,
`../cloud-bridge`; `local-runtime` → `../hardware-probe`; `assistant` →
`../router`, `../mcp-tools`). The directory names must match the ones in the
repository exactly; otherwise the chain breaks silently — which is exactly
what happened in a real CI attempt (`hardware-probe` had not been copied and
`router` returned empty stdout).

Only **runtime code** goes into the image: the package directory plus
`pyproject.toml`. `tests/` does not. Neither does `.env.local` — the
credential ITSELF is never baked into the image; only the EMPTY template
that Layer 4 places under `/etc/skel` goes in (see below). Because none of
the six modules has any third-party dependency (`dependencies = []`,
stdlib-only), this layer installs no pip or venv; the only runtime
dependency is python3 ≥ 3.11, and that is asserted during the build.

### Read-only `/usr` and bytecode

Navigator is an ostree/bootc image: on a running system `/usr` is read-only.
Python therefore cannot write `__pycache__` at runtime and recompiles the
source on every invocation — a measurable cost, since a single request in
this chain means 3-4 subprocesses. Bytecode is therefore generated at build
time:

```
python3 -m compileall -q --invalidation-mode checked-hash <path>
```

`checked-hash` is a deliberate choice and was genuinely tested: the ostree
commit normalises all file `mtime`s, so with the default timestamp-based
invalidation the `.pyc` files would be considered stale. In a local
experiment (mtimes pulled back to 1970 and the directory made read-only),
`python3 -v` output confirmed this:

- timestamp mode → `# bytecode is stale for 'hardware_probe'` +
  `could not create ... PermissionError` (recompilation on every
  invocation, cache cannot be written)
- `checked-hash` → `# ...probe.cpython-313.pyc matches ...probe.py`
  (hash-based validation is independent of mtime, the `.pyc` is used)

### Real CI evidence

This layer was verified inside a real Navigator disk image, in a VM booted
with QEMU/KVM ([run
30504082821](https://github.com/denorath-sys/navigator/actions/runs/30504082821),
`build-disk-and-boot-test.yml` → `hyprland-test`). The verification step
first tries to write to `/usr` and requires that to FAIL — meaning
everything below comes from the image itself, with no `scp` or `usroverlay`
involved:

```
OK: /usr is read-only, so everything below comes from the image.
OK: hardware-probe / local-runtime / cloud-bridge / mcp-tools / router / assistant
OK: runtime code only.                       (no tests/ or .env* leaked in)
pyc count: 36
# /usr/share/navigator/ai-stack/router/router/__pycache__/status.cpython-314.pyc
    matches /usr/share/navigator/ai-stack/router/router/status.py
OK: .pyc files are used, no recompilation at runtime.
```

The modules really ran from their path in the image (abbreviated):

```
hardware-probe: {"cpu": {"model": "AMD EPYC 7763 64-Core Processor", ...},
                 "memory": {"total_gb": 3.8}, ...}
local-runtime:  {"hardware_tier": "minimal", "ollama_available": false,
                 "model_ready": false}
cloud-bridge:   {"provider": "anthropic", "credentials_configured": false}
router:         {"route": "cloud", "reasoning": "local model not ready
                 (Ollama down or model not pulled)"}
```

Because `local-runtime`'s status report invokes its own `../hardware-probe`
sibling, and `router --decide-only` invokes `../local-runtime`, as
subprocesses, these two lines are simultaneously proof that the flat sibling
hierarchy really resolves inside the image.

In the same run, the `mcp-tools` Hyprland tools were also called against a
real compositor from their path in the image
(`/usr/share/navigator/ai-stack/mcp-tools`, read-only `/usr`), and
`shell/AssistantPanel.qml` really ran the `router` from the image:

```
list_workspaces: [{"id": 1, "name": "1", "monitor": "Virtual-1", ...}]
AssistantPanel response: [cloud] unavailable: credentials_not_configured
```

(The last line is the expected, correct behaviour: CI has neither Ollama nor
Claude credentials — a graceful failure path, not a mock.)

### Credentials

`cloud-bridge` resolves credentials from two sources, in this order of
precedence (`cloud_bridge/config.py`): first the `ANTHROPIC_API_KEY` /
`ANTHROPIC_AUTH_TOKEN` environment variables, and failing that the user's
own **`~/.config/navigator/env`** file.

The file path was not a convenience but a necessity: because `/usr` is
read-only in the real image, a file such as
`/usr/share/navigator/ai-stack/cloud-bridge/.env.local` cannot be created,
and the credential cannot be baked into the image either. The remaining
option — "let the user put it in their own session environment" — did not
actually work: the `Process` started by `shell/AssistantPanel.qml` inherits
Quickshell's environment, and Quickshell itself is started by Hyprland
`exec-once` — when the graphical session is opened from a greeter or a TTY
login there is no portable way to place a variable in that environment. The
solution is to read the credential **at the end of the chain**: because the
file is resolved relative to `HOME`, it works even when Quickshell's
environment is empty.

The template in the image: Layer 4 of `image/Containerfile` places a
commented, **empty** file (0600) at `/etc/skel/.config/navigator/env`, so
every new account finds the path in place. This was measured and then
promoted to an assertion in the boot test: both the template in the image
and the copy in the account created by bootc-image-builder are 0600 — the
user is not forced to run `chmod`. (The 0700 intended for the directory does
not hold, it comes out 755; it is the file mode that protects the secret,
details in the cloud-bridge README.) If the file is readable beyond its
owner it is DELIBERATELY ignored (ssh's private-key behaviour), and the
reason is distinguishable — `credentials_file_insecure` vs
`credentials_not_configured`; `AssistantPanel` translates these into
sentences for the user. Details: `ai-stack/cloud-bridge/README.md`, "Where
the credential comes from".

There are still no credentials in CI (and there never will be), so the
`[cloud] unavailable: credentials_not_configured` output above remains the
correct behaviour; but the credential PATH is genuinely verified in the boot
test using a fake key.

### Ollama (Layer 6)

The Ollama runtime **does** ship in the image, installed from the official
Fedora 44 repository (`0.12.11-4.fc44` — no COPR involved). The package suits
an immutable image: it declares the `ollama` user through
`/usr/lib/sysusers.d/`, so systemd creates it at boot rather than in an RPM
scriptlet, which is what an ostree deployment needs since `/var` is empty
until then. The service is enabled, so the daemon is up without the user
having to learn it exists.

**Model weights are deliberately not shipped.** A model is another ~2 GB, and
which one belongs on a machine is the user's decision — `local-runtime`
already maps a hardware tier to a recommendation (see `models.py`). Until
`ollama pull` is run the state is `model_ready: false` and `router` routes to
the cloud, which is the path this stack has had verified in CI since long
before Layer 6 existed.

The size was measured before the layer was written: ollama 55 MB compressed /
987 MB installed, plus rocblas 289 MB / 1021 MB pulled in as a hard
dependency (ollama requires `libhipblas.so.3`, so ROCm cannot be excluded
without breaking the package). That is roughly +345 MB compressed on a
3.26 GB image. It looks wasteful on a machine with no AMD card, but the
alternatives were measured too and are worse: upstream's own tarballs for the
same release are 1047 MB (rocm) and 1421 MB (default, which now bundles
CUDA).

## Status

All six modules are real and were tested with real data on this machine (not
mocks or placeholders):

- **`hardware-probe/`** — verified on real hardware: on this machine
  tier="low" (Intel i5-8500, 6 cores, 15.4 GB RAM, no discrete GPU), 20 tests.
- **`local-runtime/`** — Ollama was installed and `llama3.2:3b` pulled;
  `model_ready: true`, real `generate()` calls succeed. `chat()`/`--converse`
  were added in Phase 4 — tool-calling verified in real testing, 20 tests.
- **`router/`** — the decision layer plus local-runtime/cloud-bridge
  integration; `--decide-only`, added in Phase 4, only produces a decision
  and does not execute (so that the assistant can build its own generation
  flow). A "might this need tools?" signal was added to the complexity
  heuristic (`mentions_tool_keywords()`) — short requests relating to
  hardware, files or windows now automatically fall through to the cloud on
  a low tier (verified in real testing: on this machine "how many CPU cores
  are there?" now gets `route: "cloud"`). 38 tests.
- **`mcp-tools/`** — the MCP server (without installing the official SDK,
  stdlib-only; two transports, HTTP+SSE with Bearer token authentication)
  and 10 tools (sandboxed filesystem tools plus read-only Hyprland query
  tools), 88 tests.
- **`cloud-bridge/`** — a real Claude API key was wired up (`.env.local`,
  gitignored); multi-turn message and tool-use support were added in Phase 4
  (`send_messages()`, `--converse`). Also the **user-level credential path**
  (`~/.config/navigator/env`) — the missing piece that makes the assistant
  usable on a real desktop (see below). 50 tests.
- **`assistant/`** — the first step of Phase 4: a real conversation loop
  combining the five above. **Both the cloud and the local path now work
  with a real tool-use loop** — e.g. for "how many cores does this machine
  have?" it really runs the `hardware_tier` tool and answers correctly (on
  both). A serious security risk was caught on the local path during real
  testing (the 3B model spontaneously tried to call `write_file` with
  `overwrite=true` even on a harmless request) and was genuinely fixed — the
  write and delete tools are not shown to the local model at all, it only
  has read-only access. This and other real reliability findings are
  documented rather than hidden (see `assistant/README.md`). Conversation
  history/memory was added — in memory in the REPL, and persistent even
  across separate processes via `--history-file`. 40 tests.

All six modules are additionally **inside the real Navigator image** and are
run from that image (Containerfile Layer 5; verified in CI with `/usr`
read-only — see "Installation path in the image" above).

~256 tests in total across ai-stack. The bulk of the real integration tests
run over real subprocesses, TCP, the filesystem, Ollama and the Claude API;
those requiring credentials are designed to `skip` automatically when no
credentials can be found in any source (including CI).
