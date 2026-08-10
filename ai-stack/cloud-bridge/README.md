# ai-stack/cloud-bridge/

## What it does

The bridge that comes into play when `router/` decides the local model is
insufficient or that the user prefers the cloud. **Provider: the Anthropic
Claude API** (`claude-opus-4-8` as the default model). It provides credential
resolution (`ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN` — from an
environment variable or from the `~/.config/navigator/env` file, see "Where
the credential comes from") and a client that sends `/v1/messages` requests.

Making tool calls arriving via `mcp-tools/` work the same way for cloud
models (Phase 3+) will be this module's responsibility.

**`router` integration (Phase 2):** when the `route: "cloud"` decision is
made, `router/cloud.py` invokes this module as a subprocess with the
`--prompt` flag — see `ai-stack/router/README.md`, "cloud-bridge
integration".

## Why not the official SDK

Anthropic's official `anthropic` Python SDK (including credential
resolution, OAuth profiles and Workload Identity Federation) is the
recommended path for general-purpose Claude integrations. **Stdlib-only raw
HTTP** was deliberately chosen here because:

- The other four ai-stack modules (`hardware-probe`, `local-runtime`,
  `router`, `mcp-tools`) were written on the same principle — consistency.
- Navigator OS will ultimately be packaged via `image/Containerfile` with
  rpm-ostree/dnf; pip dependencies do not fit that model (they would require
  a separate RPM packaging step).
- Only the credential status is being reported, and no real API call is made
  yet — the SDK's real value (tool use, streaming, retry logic) is not being
  used at this point.

**Known limitation:** only `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN`
are supported — there is NO OAuth profile (`ant auth login`) or Workload
Identity Federation resolution as the official SDK provides.

## Where the credential comes from

There are two sources, in this order of precedence
(`cloud_bridge/config.py`):

1. **Environment variable** — `ANTHROPIC_API_KEY`, failing that
   `ANTHROPIC_AUTH_TOKEN`. If either is defined, the file is NEVER opened.
2. **`~/.config/navigator/env`** — the user's own file (from
   `$XDG_CONFIG_HOME` if that is defined and absolute).

### Why a file was needed

In the real image `/usr` is read-only: no `.env.local` can be placed next to
`cloud-bridge`, and the credential cannot be baked into the image either
(the image is public). That left "let the user put the variable in their own
session environment", but the chain that runs the assistant —

```
Hyprland exec-once → Quickshell → Process → python3 -m router → python3 -m cloud_bridge
```

— inherits the environment from the one the compositor was started in. When
the graphical session is opened from a greeter or a TTY login there is no
portable way to put a variable there. The credential is therefore read **at
the end of the chain, by the module that needs it**: because the file is
resolved relative to `HOME`, it works even when Quickshell's environment is
completely empty. No environment variable plumbing and no shell profile are
needed.

The image places the template itself: Layer 4 of `image/Containerfile` puts
a commented, documented and **empty** file (0600) at
`/etc/skel/.config/navigator/env` — so every new account finds the file in
place, does not have to guess the path, and image updates do not overwrite
it (`/etc/skel` is read only at account creation time).

The file's 0600 genuinely holds in the deployed image, **and it also holds
in the copy in the account created by `bootc-image-builder`** — both were
measured in the boot test and promoted to assertions ([run
30895377833](https://github.com/denorath-sys/navigator/actions/runs/30895377833)):

```
/etc/skel/.config/navigator/env  mod=600
DIAGNOSTIC RESULT: mode of the navtest copy = 600
```

So the user is not forced to run `chmod`; writing their key is enough.

The 0700 intended for the directory, however, does **not** hold:
`/etc/skel/.config/navigator` comes out as 755. The same run also narrowed
down the mechanism — it is 755 in `/usr/etc` too, so the loss happens at the
image layer/commit stage rather than in ostree's `/etc` merge during
deployment; and since the `chmod 600` in the same `RUN` does hold for the
file, this is not a plain "chmod didn't work" either. The exact mechanism is
not yet known, so the directory mode is tracked in CI as a diagnostic rather
than an assertion.

The impact is limited: someone else can list the directory and see that the
`env` file exists, but cannot read its contents — what protects the secret
is the file's mode, and `cloud-bridge` looks at the file, not the directory.

### Permissions: if they are loose the file is DELIBERATELY ignored

If the file is readable by anyone other than its owner (group/other) it is
not read — exactly ssh's private-key behaviour. Reading it silently would
mean the user never noticing that their API key is readable on a
multi-user machine. In that case the `reason` is distinguishing:

| situation | `reason` |
| --- | --- |
| neither the variable nor the file exists | `credentials_not_configured` |
| the file exists but its permissions are loose | `credentials_file_insecure` |
| the file could not be read / is not UTF-8 | `credentials_file_unreadable` |
| there is a non-`KEY=VALUE` line and no key was found at all | `credentials_file_malformed` |

`shell/AssistantPanel.qml` translates these strings into sentences for the
user (`explainReason()`) — including the "chmod 600 ~/.config/navigator/env"
advice.

### Format

Each line is `KEY=VALUE`; lines starting with `#` are comments; an optional
`export ` prefix is allowed; matching quotes around the value are stripped.
The format was deliberately kept `source`-able by a shell, but what reads it
here is NOT a shell: there are **no inline comments** (anything after `#` is
part of the value — silently truncating an API key would produce an
impossible-to-diagnose 401), no `$VAR` expansion, and no command
substitution.

A malformed line does not stop parsing: if a valid key can be found in the
remaining lines it is used, and the number of the first malformed line
appears in the status report as
`credentials_file_problem: "malformed_line:N"`.

The credential **itself** is never reported or logged; the status report
carries only its source (`credentials_source`), its path
(`credentials_file`) and the problem, if any.

## Usage

No external dependencies, only Python 3.11+ (stdlib).

```sh
cd ai-stack/cloud-bridge
python3 -m cloud_bridge --pretty                     # credential status only
python3 -m cloud_bridge --prompt "hello" --pretty    # real request (if credentials exist)
```

**`--converse`** (added in Phase 4 for `ai-stack/assistant`): reads a full
message list plus an optional `tools` schema from stdin, and prints the RAW
Claude API response (including `tool_use` blocks and `stop_reason` — unlike
`--prompt`'s simplified report) to stdout. It is for callers building a
multi-turn tool-use loop (`--prompt` remains single-turn and tool-less):

```sh
echo '{"messages": [{"role": "user", "content": "hello"}], "tools": [...]}' \
  | python3 -m cloud_bridge --converse
```

Tests:

```sh
cd ai-stack/cloud-bridge
python3 -m unittest discover -v -s tests
```

### Wiring up the credential locally (`.env.local`)

A real Anthropic API key was written to `.env.local` on this machine
(excluded by the `.env*` pattern in `.gitignore` — never committed, it
exists only on this development machine). Using it requires sourcing it
manually each time (shell state does not persist between Bash tool calls):

```sh
cd ai-stack/cloud-bridge
set -a && source .env.local && set +a
python3 -m cloud_bridge --prompt "hello" --pretty
```

`.env.local` remains a DEVELOPMENT convenience; the path on a real machine
is `~/.config/navigator/env` (see above). The difference between them comes
from the environment variable's precedence: because a sourced `.env.local`
writes into the environment, it takes priority over the file.

Credential-dependent tests (`test_prompt_cli.py`,
`router/tests/test_integration.py`) skip automatically when there are no
credentials at all (they behave this way in CI too — there are no secrets on
GitHub Actions). The "do we have credentials?" gate in those tests no longer
inspects the environment variable by hand; it calls the SAME resolution
production uses (`resolve_credentials()`). The router side does this by
asking the `python3 -m cloud_bridge` subprocess, so the rule cannot diverge
in two places.

Conversely, tests asserting that there are NO credentials now also point
`HOME` at an empty directory — otherwise the developer's own
`~/.config/navigator/env` would silently make those tests meaningless.

## Example output

With no credentials configured:

```json
{
  "schema_version": "0.1",
  "provider": "anthropic",
  "default_model": "claude-opus-4-8",
  "credentials_configured": false,
  "credentials_source": null,
  "credentials_file": "/var/home/navtest/.config/navigator/env",
  "credentials_file_problem": null
}
```

`credentials_file` is printed even when the file does not exist: so that the
user can see from the `--pretty` output which path they need to create. When
the credential is resolved from the file, `credentials_source: "file"`; when
it comes from the environment, `"environment"`.

With `--prompt` (and no credentials):

```json
{
  "schema_version": "0.1",
  "provider": "anthropic",
  "model": "claude-opus-4-8",
  "prompt_preview": "hello",
  "status": "unavailable",
  "reason": "credentials_not_configured"
}
```

With `.env.local` sourced and credentials present (verified on this machine
with a real API call; the prompt is kept verbatim as captured, which is why
it is in Turkish):

```json
{
  "schema_version": "0.1",
  "provider": "anthropic",
  "model": "claude-opus-4-8",
  "prompt_preview": "Tek kelimeyle cevap ver: Türkiye'nin başkenti neresi?",
  "status": "ok",
  "content": "Ankara"
}
```

## Why `is_available()` makes no network call

`local-runtime`'s `OllamaClient.is_available()` makes a real call to
`localhost:11434/api/version` (free, local). The Anthropic API has no free
"ping" endpoint — so `AnthropicClient.is_available()` only checks whether
the credential resolves, and does not send a real request.

Resolution is redone on every call and not cached: so that the user does not
have to restart the assistant after creating the file or fixing it with
`chmod 600`. The cost is reading a file of a few hundred bytes per call (a
single `stat` if the file does not exist).

## Out of scope — not done yet

- There is no privacy filtering (masking sensitive data before it is sent
  with the request).
- No streaming — every response is returned in full, in one go.
- There are NO credentials in CI and deliberately never will be: neither
  `.env.local` nor a real `~/.config/navigator/env` is committed, and none
  is defined as a secret on GitHub Actions. The cloud path therefore always
  reports "unavailable" in CI. Even so, the credential PATH is genuinely
  tested in CI: in the boot test a `~/.config/navigator/env` is set up
  inside the image with a FAKE key, and it is verified that resolution
  really works and that it is really refused once the permissions are
  loosened — without ever reaching out to the API.
- The credential in the file is plain text. There is NO kernel
  keyring/gnome-keyring integration; this is a deliberate first step
  (stdlib-only, no service dependency) but a real limitation.

## Status

Phase 2 — the credential/client layer, the `router` integration AND a real
Claude API credential connection are complete (`client.py`, `status.py`, and
the `python3 -m cloud_bridge [--prompt ...]` CLI). Multi-turn message and
tool-use support were added in Phase 4 (`send_messages()`, `--converse`) —
so that `ai-stack/assistant` can build a real tool-use loop. A real API key
was written to `.env.local` (gitignored) and verified end to end with real
requests — through the direct `cloud_bridge` CLI, the
`router → cloud_bridge` chain, and `assistant`'s real tool-use loop (which
genuinely called mcp-tools' `hardware_tier` tool and produced an answer with
correct hardware data).

**A user-level credential path was added** (`config.py`): this was the last
piece preventing the assistant from being usable on a real desktop — `/usr`
is read-only, and there is no portable way to put a variable into
Quickshell's environment. `~/.config/navigator/env` is now read, and the
image places the template via `/etc/skel`. It was verified end to end with a
real API key: with no `ANTHROPIC_*` variable in the environment at all, both
`cloud_bridge --prompt` directly and the `router → cloud_bridge` chain
produced a real Claude response ("Ankara") using only the credential
resolved from the file. The permission refusal was verified with a real
attempt too: with the same file set to `chmod 644`,
`reason: credentials_file_insecure`.

50 tests pass (mocked HTTP + real CLI integration tests + `test_config.py`,
where credential resolution is tested with real files and real permissions
under a temporary `HOME`; the credential-less path always runs, and the
real-API tests requiring credentials skip automatically when none can be
found).
