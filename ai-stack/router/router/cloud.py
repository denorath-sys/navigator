"""Invokes cloud-bridge as a subprocess — when the routing decision is "cloud"."""
import json
import subprocess

CLOUD_BRIDGE_CMD = ["python3", "-m", "cloud_bridge"]


def call_cloud_bridge(prompt: str, cwd: str | None = None) -> dict:
    result = subprocess.run(
        CLOUD_BRIDGE_CMD + ["--prompt", prompt],
        cwd=cwd, capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)
