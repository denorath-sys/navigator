"""Donanım sinyallerini bir Navigator AI model tier'ına eşler.

Eşikler Faz 2 taslağıdır — `local-runtime` gerçek model benchmark verisi
ürettikçe (Faz 3+) yeniden ayarlanacaktır.

  - "minimal": RAM < 8 GB, ayrık GPU yok        → sadece bulut önerilir
  - "low":     RAM >= 8 GB, ayrık GPU eşiği yok  → küçük yerel model (~3B)
  - "mid":     RAM >= 16 GB ve VRAM >= 6 GB      → orta model (~8B)
  - "high":    RAM >= 32 GB ve VRAM >= 12 GB     → büyük model (~14B+)
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
        reason = f"RAM {memory_gb} GB >= 32 ve dedicated VRAM {vram_gb} GB >= 12"
    elif memory_gb >= 16 and vram_gb >= 6:
        tier = "mid"
        reason = f"RAM {memory_gb} GB >= 16 ve dedicated VRAM {vram_gb} GB >= 6"
    elif memory_gb >= 8:
        tier = "low"
        reason = f"RAM {memory_gb} GB >= 8 ama mid eşiği (16 GB + 6 GB VRAM) karşılanmadı"
    else:
        tier = "minimal"
        reason = f"RAM {memory_gb} GB < 8 — yerel model önerilmez"

    return {
        "tier": tier,
        "has_dedicated_gpu": has_dedicated_gpu,
        "best_gpu_vram_gb": vram_gb,
        "reasoning": reason,
    }
