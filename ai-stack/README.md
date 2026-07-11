# ai-stack/

Navigator'ı "AI-native" yapan katman. Yapay zekayı üçüncü parti bir uygulama
olarak değil, işletim sisteminin doğal bir parçası olarak sunmayı hedefler.

Beş bileşenden oluşur, her biri kendi README'sinde detaylandırılmıştır:

| Modül | Sorumluluk |
|---|---|
| [`hardware-probe/`](hardware-probe/README.md) | Donanımı tespit eder, model tier'ını belirler |
| [`local-runtime/`](local-runtime/README.md) | Yerel model çalıştırma (llama.cpp/Ollama) |
| [`mcp-tools/`](mcp-tools/README.md) | MCP tabanlı sistem/araç erişimi |
| [`router/`](router/README.md) | Yerel↔bulut hibrit istek yönlendirme |
| [`cloud-bridge/`](cloud-bridge/README.md) | Bulut model sağlayıcılarına bağlantı |

## Veri akışı (hedeflenen, Faz 2+)

```
kullanıcı isteği (shell/ asistan paneli)
        │
        ▼
    router/  ──► hardware-probe/ (tier kararı)
        │
        ├──► local-runtime/  (yerel model yeterliyse)
        │
        └──► cloud-bridge/   (yerel yetersiz/kullanıcı tercih ederse)
                     │
                     ▼
              mcp-tools/ (her iki yolda da araç çağrıları için ortak katman)
```

## Durum

Faz 1 — sadece mimari niyet ve modül sınırları belgeleniyor. Kod yok.
İlk implementasyon Faz 2'de `hardware-probe/` ile başlayacak (diğer tüm
modüller donanım tier kararına bağımlı).
