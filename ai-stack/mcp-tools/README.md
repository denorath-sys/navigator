# ai-stack/mcp-tools/

## What it does

The tool layer that lets the Navigator assistant interact with the system.
Using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io)
standard, it gives both local and cloud models access to the same tool set
through a single interface — tool calls run through this module regardless
of which model `router/` picked.

**Architectural decision (Phase 2):** the MCP protocol was implemented
stdlib-only, without installing the official `mcp` Python SDK — preserving
the same "no external dependencies" principle as the other ai-stack modules.
Two transports are supported, both sharing the same
`MCPServer.handle_message()` logic:

- **stdio** (default) — newline-delimited JSON-RPC 2.0
- **HTTP+SSE** (`--http`) — the classic two-endpoint model (`GET /sse` +
  `POST /messages`), via `http.server` (see "HTTP+SSE transport" below)

## Tools

Ten tools are registered — two wrapping other, already working ai-stack
modules, five providing sandboxed filesystem access, and three querying
Hyprland compositor state read-only:

| Tool | Description |
|---|---|
| `hardware_tier` | Wraps `hardware-probe` — returns the hardware tier and the CPU/RAM/GPU signals |
| `route_request` | Wraps `router` — decides whether a request is served locally or by the cloud (it now also triggers the real local generation / cloud call) |
| `read_file` | Reads a file's contents — **sandboxed** |
| `list_directory` | Lists a directory's contents — **sandboxed** |
| `write_file` | Writes text content to a file — **sandboxed**, `overwrite=true` required to write over an existing file |
| `delete_file` | Deletes a file — **sandboxed**, irreversible, `confirm=true` required |
| `rename_file` | Renames/moves a file — **sandboxed** (both source and destination), `overwrite=true` required if the destination already exists |
| `list_windows` | Lists open Hyprland windows — **read-only** (`hyprctl -j clients`) |
| `list_workspaces` | Lists Hyprland workspaces — **read-only** (`hyprctl -j workspaces`) |
| `active_window` | Returns information about the focused window — **read-only** (`hyprctl -j activewindow`) |

### Filesystem tools — the security model

All the filesystem tools (`filesystem.py`) were deliberately designed with a
narrow authority surface:

- **Files only** — no tool deletes or renames a directory; given a directory
  path they return an error. The scope is deliberately kept narrow.
- **A sandboxed root directory** — all paths are resolved relative to a root
  directory (default: the user's home directory, overridable with the
  `NAVIGATOR_MCP_FS_ROOT` environment variable); they are reduced to
  canonical form with `os.path.realpath` and verified not to escape the
  root. Path traversal with `../` and attempts to give an absolute path
  outside the root are blocked (tested over the real MCP protocol — see the
  tests). This check applies identically to `write_file`, `delete_file` and
  `rename_file` (both source and destination).
- **Extra protections for writing** — `write_file` can only write over an
  existing file with `overwrite=true` (to prevent accidental data loss); the
  parent directory must already exist (the tool does not create directories
  on its own, keeping its scope limited to file content); and attempting to
  write to a directory path returns an error.
- **An extra protection for deletion** — because `delete_file` is
  irreversible it deletes nothing without `confirm=true`; if called
  accidentally (including the LLM triggering it on its own) it returns an
  error by default.
- **An extra protection for renaming** — `rename_file` is consistent with
  `write_file`: `overwrite=true` is required if the destination already
  exists, and the destination's parent directory must already exist.
- **Size limits** — `read_file` reads at most ~1 MB (`MAX_READ_BYTES`),
  `write_file` writes at most ~1 MB (`MAX_WRITE_BYTES`), and
  `list_directory` returns at most 500 entries (`MAX_LIST_ENTRIES`) — to
  keep large files and directories from drowning the context.

### Hyprland tools — scope and limitations

`list_windows`, `list_workspaces` and `active_window` (`hyprland.py`) are
deliberately **read-only** — there are NO dispatch commands such as
switching workspace or closing/moving a window. They invoke
`hyprctl -j <command>` as a subprocess and return its JSON output.

Because the development environment is Debian/Pardus (Hyprland is not
packaged there), these three tools cannot be tested on the local machine —
but they were verified against a REAL Hyprland compositor in CI (see below).
In addition to that:

1. They were unit-tested with mocked `subprocess.run`/`shutil.which`
   (`tests/test_hyprland.py`).
2. In a real stdio MCP session it was verified that, with Hyprland not
   running, the tools fail gracefully with a clear error
   (`isError: true`, a `HyprlandError` message) rather than crashing
   (`tests/test_hyprland_integration.py`) — the same pattern as verifying
   cloud-bridge's credential-less path.

**Verified against a real compositor (CI, 2026-07-18):** the
`hyprland-test` job in `.github/workflows/build-disk-and-boot-test.yml`
boots a real Navigator disk image in QEMU (`virtio-gpu-pci` +
`-display vnc`, requiring no GPU/EGL on the host — the guest renders in
software with its own Mesa/llvmpipe), really starts Hyprland, and calls the
`mcp_tools.hyprland` functions directly. Two real problems came up along the
way and were solved:

- Hyprland deliberately refuses to run as root — CI only has root SSH
  access, so this was worked around with the `--i-am-really-stupid` flag.
- aquamarine's DRM backend tries to open a seat with
  `libseat_open_seat()`; because an SSH session has no real seat in
  systemd-logind, this was failing (`CBackend::create() failed!`). The
  `seatd` package was missing from the image (`rpm -q seatd` → "package
  seatd is not installed", `loginctl` → a "-" in the SEAT column); the
  package was added (`image/Containerfile`) and the test script starts
  seatd in the background before Hyprland and sets `LIBSEAT_BACKEND=seatd`.

The result — real `hyprctl monitors` output (the QEMU virtual monitor):

```
Monitor Virtual-1 (ID 0):
	1280x800@74.99400 at 0x0
	description: Red Hat Inc. QEMU Monitor
	...
	focused: yes
```

And real `mcp_tools.hyprland` calls (not mocks):

```
list_windows: []
list_workspaces: [{"id": 1, "name": "1", "monitor": "Virtual-1", "monitorID": 0, "windows": 0, "hasfullscreen": false, "lastwindow": "0x0", "lastwindowtitle": "", "ispersistent": false}]
active_window: {}
```

(`list_windows` and `active_window` come back empty because no window was
opened — expected behaviour, not an error: `hyprctl -j activewindow`
returns `{}` when there is no focused window, and `active_window()` passes
that through without raising a `HyprlandError`.)

## Usage

No external dependencies, only Python 3.11+ (stdlib). It must sit next to
`hardware-probe` and `router` (as sibling directories).

Starting the server over stdio (the default):

```sh
cd ai-stack/mcp-tools
python3 -m mcp_tools
```

Starting it over HTTP+SSE (authentication is mandatory, see the section
below):

```sh
cd ai-stack/mcp-tools
python3 -m mcp_tools --http --port 8765   # the address can also be changed with --host
# if no token is given one is generated automatically and printed to stderr;
# for a fixed token: --token <TOKEN> or the NAVIGATOR_MCP_HTTP_TOKEN env var
```

To change the root directory of the filesystem tools (default: the home
directory):

```sh
NAVIGATOR_MCP_FS_ROOT=/your/root python3 -m mcp_tools
```

Over stdio: newline-delimited JSON-RPC messages are written to stdin and
responses are read the same way from stdout (see the example session in
`tests/test_integration.py`: `initialize` → `notifications/initialized` →
`tools/list` → `tools/call`).

Tests:

```sh
cd ai-stack/mcp-tools
python3 -m unittest discover -v -s tests
```

## A real session example

A real stdio session was run on this machine (against an isolated sandbox
directory, via `NAVIGATOR_MCP_FS_ROOT`):

```
tools/list -> ["hardware_tier", "route_request", "read_file", "list_directory", "write_file", "delete_file", "rename_file", "list_windows", "list_workspaces", "active_window"]
tools/call(read_file, {"path": "hello.txt"}) -> {"content": [{"type": "text", "text": "hello navigator"}], "isError": false}
tools/call(list_directory, {}) -> {"content": [{"type": "text", "text": "[{\"name\": \"hello.txt\", ...}, {\"name\": \"subdir\", ...}]"}], "isError": false}
tools/call(read_file, {"path": "../../../../etc/passwd"}) -> {"content": [{"type": "text", "text": "Tool error: '...' escapes the permitted root directory (...)"}], "isError": true}
tools/call(write_file, {"path": "new.txt", "content": "navigator wrote this"}) -> {"content": [{"type": "text", "text": "20 bytes written: new.txt"}], "isError": false}
tools/call(write_file, {"path": "new.txt", "content": "again"}) -> {"content": [{"type": "text", "text": "Tool error: File already exists: new.txt (overwrite=true is required to write over it)"}], "isError": true}
tools/call(rename_file, {"path": "new.txt", "new_path": "renamed.txt"}) -> {"content": [{"type": "text", "text": "Renamed: new.txt -> renamed.txt"}], "isError": false}
tools/call(delete_file, {"path": "renamed.txt"}) -> {"content": [{"type": "text", "text": "Tool error: Deletion is irreversible — confirm=true is required to confirm: renamed.txt"}], "isError": true}
tools/call(delete_file, {"path": "renamed.txt", "confirm": true}) -> {"content": [{"type": "text", "text": "Deleted: renamed.txt"}], "isError": false}
tools/call(list_windows, {}) -> {"content": [{"type": "text", "text": "Tool error: Hyprland is not running (HYPRLAND_INSTANCE_SIGNATURE is not set)"}], "isError": true}
```

(`list_windows` errors on this machine as expected — Hyprland does not run
here. On a real compositor `isError: false` and a real window list are
expected, to be verified in Phase 3.)

The `mcp-tools → router → local-runtime → hardware-probe` chain also works
end to end over the real MCP protocol (see the `route_request` tool) —
identically on both the stdio and the HTTP+SSE transport.

## HTTP+SSE transport

`http_transport.py` implements the classic HTTP+SSE model from MCP's
2024-11-05 specification (not the newer "Streamable HTTP" — `server.py`
already advertises `protocolVersion: "2024-11-05"`, so this is consistent):

1. The client connects to `GET /sse` — the server generates a `session_id`,
   announces the URI the client should POST to
   (`/messages?session_id=<id>`) via a first `endpoint` event, and then
   keeps the connection open.
2. The client `POST`s JSON-RPC requests to that URI — the server handles the
   request with the same `MCPServer.handle_message()`, **does not return the
   response in the HTTP body** (only `202 Accepted`), and instead adds it to
   the session's queue.
3. The queued response flows asynchronously as a `message` event over the
   SSE connection opened in step 1.

Because `ThreadingHTTPServer` is used, every connection (including the
long-lived SSE GET) runs in its own thread — POST requests do not block the
SSE connection. A POST with an unknown or missing `session_id` → `400`.

A real HTTP+SSE session (real TCP sockets, subprocess) was run end to end on
this machine: endpoint discovery → `initialize`/`tools/list`/`tools/call`
POSTs → responses over SSE with correct `id` matching.

## Authentication (HTTP+SSE)

The stdio transport needs no authentication, being a local process pipeline
(OS process isolation is sufficient). But because HTTP+SSE opens a TCP
socket (even if bound to `127.0.0.1` by default), the Bearer token
verification implemented in `auth.py` is mandatory:

- **No unauthenticated operation.** If `--token` is not given and the
  `NAVIGATOR_MCP_HTTP_TOKEN` environment variable is not set, the server
  generates a token automatically with `secrets.token_urlsafe(32)` and
  prints it to stderr at start-up — it never silently runs as an open door
  (the same principle as Jupyter's notebook token model).
- **Both endpoints are protected** — `GET /sse` and `POST /messages` return
  `401` (together with a `WWW-Authenticate: Bearer` header) if the
  `Authorization: Bearer <token>` header is missing or wrong.
- **Timing-attack-resistant comparison** — `hmac.compare_digest` is used,
  not a plain `==`.
- Token precedence: the `--token` CLI argument > `NAVIGATOR_MCP_HTTP_TOKEN`
  > automatic generation.

Verified over real TCP: a full MCP session (SSE + POST) with the correct
token, and `401` on both endpoints with no token or a wrong token (see
`tests/test_http_transport_integration.py`).

## Out of scope — not done yet

- No directory deletion/renaming/creation — files only (`write_file` does
  not create a new directory either; the parent must already exist).
- No Hyprland **control** commands — queries only (`list_windows`,
  `list_workspaces`, `active_window`). Dispatch commands such as switching
  workspace or focusing/closing/moving a window were deliberately not added
  (a wider authority surface; real Hyprland can now be tested in CI, but
  that has not yet made widening the scope necessary).
- No tools that talk to Quickshell.
- The Hyprland tools cannot be tested on this (Debian/Pardus) machine, but
  all three (`list_windows`, `list_workspaces`, `active_window`) were
  verified against a real compositor in CI — see "Hyprland tools — scope and
  limitations".
- No TLS/HTTPS — the Bearer token travels over plain HTTP; it is only safe
  under the current `127.0.0.1` assumption, and TLS is essential for
  externally exposed use.
- MCP's newer "Streamable HTTP" transport is not supported — only the
  classic HTTP+SSE (2024-11-05).

## Status

Phase 2 — the MCP server (`protocol.py`, `server.py`, `tools.py`), the
filesystem tools (`filesystem.py` — reading, listing, controlled writing,
deletion AND renaming), the HTTP+SSE transport (`http_transport.py`), Bearer
token authentication (`auth.py`) AND the Hyprland query tools (`hyprland.py`
— read-only, verified with mocked and graceful-failure tests) are complete,
with a `python3 -m mcp_tools [--http] [--token T]` CLI.
88 tests pass (protocol round-trip, server dispatch, tool tests against the
real modules, filesystem tests including path traversal blocking, overwrite
protection and the confirm requirement, session registry unit tests, auth
helper function tests, mocked Hyprland tests, and end-to-end MCP protocol
tests over both transports with real subprocesses and TCP sockets —
including authenticated and unauthenticated requests and Hyprland's graceful
failure path).
