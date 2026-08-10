"""Navigator's first MCP tools — wrapping hardware-probe and router.

Both tools invoke the relevant module's CLI over a subprocess (the same
pattern as in ai-stack/router/router/status.py) — using the CLI rather than a
Python import is closer to how they will run as separate processes on a real
system.
"""
import subprocess

HARDWARE_PROBE_CMD = ["python3", "-m", "hardware_probe"]
ROUTER_CMD = ["python3", "-m", "router"]


def hardware_tier_tool(hardware_probe_path: str = "../hardware-probe") -> str:
    result = subprocess.run(
        HARDWARE_PROBE_CMD, cwd=hardware_probe_path, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def route_request_tool(
    prompt: str, prefer: str = "balanced", router_path: str = "../router"
) -> str:
    result = subprocess.run(
        ROUTER_CMD + ["--prompt", prompt, "--prefer", prefer],
        cwd=router_path,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def register_default_tools(
    server, hardware_probe_path: str = "../hardware-probe", router_path: str = "../router"
) -> None:
    server.register_tool(
        name="hardware_tier",
        description=(
            "Returns the AI model tier (minimal/low/mid/high) of the "
            "hardware Navigator runs on, plus the CPU/RAM/GPU signals."
        ),
        input_schema={"type": "object", "properties": {}},
        handler=lambda: hardware_tier_tool(hardware_probe_path),
    )
    server.register_tool(
        name="route_request",
        description=(
            "Decides whether a user request should be served by the local "
            "model or by the cloud."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The request to route"},
                "prefer": {
                    "type": "string",
                    "enum": ["balanced", "privacy", "cost", "speed"],
                    "default": "balanced",
                },
            },
            "required": ["prompt"],
        },
        handler=lambda prompt, prefer="balanced": route_request_tool(prompt, prefer, router_path),
    )
