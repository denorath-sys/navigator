"""local-runtime durumunu sorgulayıp routing kararını üretir; karara göre
local-runtime veya cloud-bridge'i gerçekten çağırır.

router, hardware-probe'u ayrıca çağırmaz — local-runtime'ın raporu zaten
hardware_tier ve model_ready alanlarını içeriyor (bkz.
ai-stack/local-runtime/local_runtime/status.py), tek bir subprocess hop'u
yeterli.
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
    )

    report = {
        "schema_version": SCHEMA_VERSION,
        "prompt_preview": prompt[:80],
        "complexity": complexity,
        "preference": preference,
        "hardware_tier": status["hardware_tier"],
        "model_ready": status["model_ready"],
        "route": decision["target"],
        "reasoning": decision["reasoning"],
    }

    if decide_only:
        # Sadece karar üretir, local-runtime/cloud-bridge'i ÇALIŞTIRMAZ —
        # ai-stack/assistant gibi çağıranların kendi üretim akışını (örn.
        # tool-use döngüsü) kurabilmesi, gereksiz/israf bir bulut çağrısı
        # yapılmadan.
        return report

    if decision["target"] == "cloud":
        caller = cloud_bridge_caller or call_cloud_bridge
        report["cloud_bridge"] = caller(prompt, cwd=cloud_bridge_cwd)
    else:
        caller = local_runtime_caller or call_local_runtime
        report["local_runtime"] = caller(prompt, cwd=local_runtime_cwd)

    return report
