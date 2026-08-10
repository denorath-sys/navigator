"""Tools that query Hyprland compositor state — read-only.

Wraps `hyprctl`'s JSON output mode (`hyprctl -j <command>`). There are
deliberately QUERIES ONLY — NO dispatch commands such as switching workspace
or closing/moving a window (the scope was deliberately kept narrow in
Phase 2, see mcp-tools/README.md, "Out of scope").

Because the development environment is Debian/Pardus (Hyprland is not
packaged there), these tools cannot be tested on the local machine — but
they were verified against a real Hyprland compositor in CI
(`build-disk-and-boot-test.yml`, the `hyprland-test` job), in addition to
the mocked subprocess tests (see `mcp-tools/README.md`, "Hyprland tools —
scope and limitations").
"""
import json
import os
import shutil
import subprocess

HYPRCTL_BIN = "hyprctl"
TIMEOUT = 5.0


class HyprlandError(Exception):
    """Raised when Hyprland cannot be reached (not installed, not running, hyprctl error)."""


def _run_hyprctl(*args: str) -> object:
    if shutil.which(HYPRCTL_BIN) is None:
        raise HyprlandError("hyprctl not found — Hyprland is not installed")
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        raise HyprlandError("Hyprland is not running (HYPRLAND_INSTANCE_SIGNATURE is not set)")

    try:
        result = subprocess.run(
            [HYPRCTL_BIN, "-j", *args],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired as e:
        raise HyprlandError(f"hyprctl timed out: {e}") from e
    except OSError as e:
        raise HyprlandError(f"could not run hyprctl: {e}") from e

    if result.returncode != 0:
        raise HyprlandError(f"hyprctl returned an error: {result.stderr.strip()}")

    try:
        return json.loads(result.stdout)
    except ValueError as e:
        raise HyprlandError(f"hyprctl output is not JSON: {e}") from e


def list_windows() -> list[dict]:
    return _run_hyprctl("clients")


def list_workspaces() -> list[dict]:
    return _run_hyprctl("workspaces")


def active_window() -> dict:
    return _run_hyprctl("activewindow")


def register_hyprland_tools(server) -> None:
    server.register_tool(
        name="list_windows",
        description="Lists open Hyprland windows (read-only, hyprctl -j clients).",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=lambda: json.dumps(list_windows(), ensure_ascii=False),
    )
    server.register_tool(
        name="list_workspaces",
        description="Lists Hyprland workspaces (read-only, hyprctl -j workspaces).",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=lambda: json.dumps(list_workspaces(), ensure_ascii=False),
    )
    server.register_tool(
        name="active_window",
        description=(
            "Returns information about the currently focused Hyprland window "
            "(read-only, hyprctl -j activewindow)."
        ),
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=lambda: json.dumps(active_window(), ensure_ascii=False),
    )
