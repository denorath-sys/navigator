"""Maps hardware signals to a Navigator AI model tier.

The thresholds are a Phase 2 draft — they will be retuned (Phase 3+) as
`local-runtime` produces real model benchmark data.

  - "minimal": RAM < 8 GB, no discrete GPU        → cloud only is recommended
  - "low":     RAM >= 8 GB, discrete GPU threshold not met → small local model (~3B)
  - "mid":     RAM >= 16 GB and VRAM >= 6 GB      → medium model (~8B)
  - "high":    RAM >= 32 GB and VRAM >= 12 GB     → large model (~14B+)
"""

TIERS = ("minimal", "low", "mid", "high")


def best_gpu_vram_gb(gpu_devices: list[dict]) -> float:
    dedicated_vram = [
        d["vram_gb"]
        for d in gpu_devices
        if d.get("dedicated") and d.get("vram_gb") is not None
    ]
    return max(dedicated_vram, default=0.0)


def decide_tier(memory_gb: float, gpu_devices: list[dict]) -> dict:
    vram_gb = best_gpu_vram_gb(gpu_devices)
    has_dedicated_gpu = any(d.get("dedicated") for d in gpu_devices)

    if memory_gb >= 32 and vram_gb >= 12:
        tier = "high"
        reason = f"RAM {memory_gb} GB >= 32 and dedicated VRAM {vram_gb} GB >= 12"
    elif memory_gb >= 16 and vram_gb >= 6:
        tier = "mid"
        reason = f"RAM {memory_gb} GB >= 16 and dedicated VRAM {vram_gb} GB >= 6"
    elif memory_gb >= 8:
        tier = "low"
        reason = f"RAM {memory_gb} GB >= 8 but the mid threshold (16 GB + 6 GB VRAM) was not met"
    else:
        tier = "minimal"
        reason = f"RAM {memory_gb} GB < 8 — no local model recommended"

    return {
        "tier": tier,
        "has_dedicated_gpu": has_dedicated_gpu,
        "best_gpu_vram_gb": vram_gb,
        "reasoning": reason,
    }
