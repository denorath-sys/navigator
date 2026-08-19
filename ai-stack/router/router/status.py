"""Query the local-runtime status and produce the routing decision; then
genuinely invoke local-runtime or cloud-bridge according to that decision.

The router does not call hardware-probe separately — local-runtime's report
already contains the hardware_tier, model_ready and ollama_available fields
(see ai-stack/local-runtime/local_runtime/status.py), so a single subprocess
hop is enough.
"""
import json
import subprocess

from .cloud import call_cloud_bridge
from .decision import decide_route, estimate_complexity
from .local import call_local_runtime

SCHEMA_VERSION = "0.1"
LOCAL_RUNTIME_CMD = ["python3", "-m", "local_runtime"]


def get_local_runtime_status(cwd: str | None = None) -> dict:
    result = subprocess.run(
        LOCAL_RUNTIME_CMD, cwd=cwd, capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def route_request(
    prompt: str,
    preference: str = "balanced",
    local_runtime_cwd: str | None = None,
    cloud_bridge_cwd: str | None = None,
    status: dict | None = None,
    cloud_bridge_caller=None,
    local_runtime_caller=None,
    decide_only: bool = False,
) -> dict:
    status = status or get_local_runtime_status(cwd=local_runtime_cwd)
    complexity = estimate_complexity(prompt)
    decision = decide_route(
        hardware_tier=status["hardware_tier"],
        model_ready=status["model_ready"],
        preference=preference,
        complexity=complexity,
        # local-runtime reports this separately and the router used to throw
        # it away, which is why "not ready" could not say which kind. .get()
        # rather than [] because a caller may pass a partial status dict, and
        # an unreported field is a vaguer sentence rather than a crash.
        ollama_available=status.get("ollama_available"),
    )

    report = {
        "schema_version": SCHEMA_VERSION,
        "prompt_preview": prompt[:80],
        "complexity": complexity,
        "preference": preference,
        "hardware_tier": status["hardware_tier"],
        "model_ready": status["model_ready"],
        "ollama_available": status.get("ollama_available"),
        "route": decision["target"],
        "reasoning": decision["reasoning"],
    }

    if decide_only:
        # Produces the decision only, and DOES NOT RUN
        # local-runtime/cloud-bridge — so that callers such as
        # ai-stack/assistant can build their own generation flow (e.g. a
        # tool-use loop) without a wasteful, unnecessary cloud call.
        return report

    if decision["target"] == "cloud":
        caller = cloud_bridge_caller or call_cloud_bridge
        report["cloud_bridge"] = caller(prompt, cwd=cloud_bridge_cwd)
    else:
        caller = local_runtime_caller or call_local_runtime
        report["local_runtime"] = caller(prompt, cwd=local_runtime_cwd)

    return report
