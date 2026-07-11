"""Hardware tier'ından önerilen yerel Ollama modeline eşleme.

Taslak eşleme (Faz 2) — model AĞIRLIKLARI burada indirilmiyor, sadece isim
önerisi üretiliyor. Gerçek indirme ayrı bir onay adımı gerektirir (bkz.
README.md "İndirme gerektiren kısım"). Eşleme, `local-runtime` gerçek
kullanım/benchmark verisi biriktikçe Faz 3+'ta revize edilecek.
"""

TIER_MODEL_MAP = {
    "minimal": None,  # yerel model önerilmez — router cloud-bridge'e yönlendirmeli
    "low": {"model": "llama3.2:3b", "approx_size_gb": 2.0},
    "mid": {"model": "llama3.1:8b", "approx_size_gb": 4.7},
    "high": {"model": "llama3.1:70b", "approx_size_gb": 40.0},
}


def recommend_model(tier: str) -> dict | None:
    if tier not in TIER_MODEL_MAP:
        raise ValueError(f"Bilinmeyen tier: {tier!r}")
    return TIER_MODEL_MAP[tier]
