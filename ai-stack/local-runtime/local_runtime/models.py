"""Mapping from the hardware tier to a recommended local Ollama model.

A draft mapping (Phase 2) — no model WEIGHTS are downloaded here, only a name
recommendation is produced. A real download requires a separate approval step
(see README.md). The mapping will be revised in Phase 3+ as `local-runtime`
accumulates real usage and benchmark data.
"""

TIER_MODEL_MAP = {
    "minimal": None,  # no local model recommended — the router should route to cloud-bridge
    "low": {"model": "llama3.2:3b", "approx_size_gb": 2.0},
    "mid": {"model": "llama3.1:8b", "approx_size_gb": 4.7},
    "high": {"model": "llama3.1:70b", "approx_size_gb": 40.0},
}


def recommend_model(tier: str) -> dict | None:
    if tier not in TIER_MODEL_MAP:
        raise ValueError(f"Bilinmeyen tier: {tier!r}")
    return TIER_MODEL_MAP[tier]
