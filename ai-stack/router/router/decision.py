"""Saf yönlendirme mantığı — I/O yok, tamamen test edilebilir fonksiyonlar.

Eşikler/kurallar Faz 2 taslağıdır; gerçek kullanım verisi (hangi isteklerin
yerelde başarısız kaldığı, kullanıcı geri bildirimi) biriktikçe Faz 3+'ta
revize edilecek.
"""

PREFERENCES = ("balanced", "privacy", "cost", "speed")
LOW_CAPABILITY_TIERS = ("minimal", "low")

# Bir isteğin mcp-tools'un araçlarını (donanım/dosya sistemi/Hyprland sorgu)
# gerektirebileceğini işaret eden kaba bir anahtar kelime kümesi.
# ai-stack/assistant'ta gerçek testte doğrulandı: bu makinede (tier="low")
# kısa ama araç gerektiren istekler ("kaç CPU çekirdeği var?") sadece kelime
# sayısına bakan eski sezgiyle yerele düşüyordu, ve küçük yerel modelin
# tool-use güvenilirliği düşük olduğundan (bkz. assistant/README.md "Yerel
# tool-use") bazen hatalı/alakasız cevap üretiyordu. Bu yüzden bu tür
# istekler de 'complex' sayılıp (düşük tier'da) buluta yönlendiriliyor.
TOOL_KEYWORDS = (
    # donanım
    "çekirdek",
    "cpu",
    "ram",
    "bellek",
    "gpu",
    "grafik kart",
    "donanım",
    "tier",
    # dosya sistemi
    "dosya",
    "klasör",
    "dizin",
    "listele",
    # pencere/masaüstü (Hyprland)
    "pencere",
    "workspace",
    "masaüstü",
    # genel araç işareti
    "aracı",
    "aracını",
    "aracıyla",
)


def mentions_tool_keywords(prompt: str) -> bool:
    """Prompt, mcp-tools'un araçlarını gerektirebilecek bir konudan
    (donanım/dosya/pencere) bahsediyor mu — kaba bir anahtar kelime
    taraması. Gerçek bir niyet sınıflandırması değil (bkz. modül
    docstring'i), ama kelime sayısından daha isabetli bir ilk sinyal."""
    lowered = prompt.lower()
    return any(keyword in lowered for keyword in TOOL_KEYWORDS)


def estimate_complexity(prompt: str) -> str:
    """Çok kaba bir taslak sezgisel: uzun/çok satırlı istekler VEYA araç
    gerektirebilecek istekler 'complex' sayılır.

    Gerçek bir sınıflandırma (token sayısı, geçmiş bağlam uzunluğu, gerçek
    niyet tespiti) Faz 3+'ta ele alınacak.
    """
    if "\n" in prompt:
        return "complex"
    if len(prompt.split()) > 40:
        return "complex"
    if mentions_tool_keywords(prompt):
        return "complex"
    return "simple"


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
                "reasoning": (
                    "hız tercihi + karmaşık/araç gerektirebilecek istek + düşük donanım "
                    "tier'ı: bulut daha hızlı ve güvenilir yanıt verebilir"
                ),
            }
        return {
            "target": "local",
            "reasoning": "hız tercihi: ağ gecikmesi olmadan yerel model yeterli",
        }

    # preference == "balanced" (varsayılan)
    if complexity == "complex" and hardware_tier in LOW_CAPABILITY_TIERS:
        return {
            "target": "cloud",
            "reasoning": (
                "karmaşık/araç gerektirebilecek istek + düşük donanım tier'ı: yerel model "
                "yetersiz kalabilir veya tool-use güvenilirliği düşük olabilir"
            ),
        }
    return {
        "target": "local",
        "reasoning": "model hazır ve istek yerel için uygun",
    }
