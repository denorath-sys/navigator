"""Saf yönlendirme mantığı — I/O yok, tamamen test edilebilir fonksiyonlar.

Eşikler/kurallar Faz 2 taslağıdır; gerçek kullanım verisi (hangi isteklerin
yerelde başarısız kaldığı, kullanıcı geri bildirimi) biriktikçe Faz 3+'ta
revize edilecek.
"""

PREFERENCES = ("balanced", "privacy", "cost", "speed")
LOW_CAPABILITY_TIERS = ("minimal", "low")


def estimate_complexity(prompt: str) -> str:
    """Çok kaba bir taslak sezgisel: uzun/çok satırlı istekler 'complex' sayılır.

    Gerçek bir sınıflandırma (token sayısı, araç çağrısı ihtiyacı, geçmiş
    bağlam uzunluğu) Faz 3+'ta ele alınacak.
    """
    if "\n" in prompt:
        return "complex"
    return "complex" if len(prompt.split()) > 40 else "simple"


def decide_route(hardware_tier: str, model_ready: bool, preference: str, complexity: str) -> dict:
    if preference not in PREFERENCES:
        raise ValueError(f"Bilinmeyen tercih: {preference!r} (geçerli: {PREFERENCES})")

    if not model_ready:
        return {
            "target": "cloud",
            "reasoning": "yerel model hazır değil (Ollama kapalı veya model indirilmemiş)",
        }

    if preference == "privacy":
        return {
            "target": "local",
            "reasoning": "gizlilik tercihi: model hazır olduğu sürece her zaman yerel",
        }

    if preference == "cost":
        return {
            "target": "local",
            "reasoning": "maliyet tercihi: model hazır olduğu sürece her zaman yerel (ücretsiz)",
        }

    if preference == "speed":
        if complexity == "complex" and hardware_tier in LOW_CAPABILITY_TIERS:
            return {
                "target": "cloud",
                "reasoning": "hız tercihi + karmaşık istek + düşük donanım tier'ı: bulut daha hızlı yanıt verebilir",
            }
        return {
            "target": "local",
            "reasoning": "hız tercihi: ağ gecikmesi olmadan yerel model yeterli",
        }

    # preference == "balanced" (varsayılan)
    if complexity == "complex" and hardware_tier in LOW_CAPABILITY_TIERS:
        return {
            "target": "cloud",
            "reasoning": "karmaşık istek + düşük donanım tier'ı: yerel model yetersiz kalabilir",
        }
    return {
        "target": "local",
        "reasoning": "model hazır ve istek yerel için uygun",
    }
