# ai-stack/

Navigator'ı "AI-native" yapan katman. Yapay zekayı üçüncü parti bir uygulama
olarak değil, işletim sisteminin doğal bir parçası olarak sunmayı hedefler.

Beş bileşenden oluşur, her biri kendi README'sinde detaylandırılmıştır:

| Modül | Sorumluluk |
|---|---|
| [`hardware-probe/`](hardware-probe/README.md) | Donanımı tespit eder, model tier'ını belirler — **Faz 2: ilk implementasyon hazır** |
| [`local-runtime/`](local-runtime/README.md) | Yerel model çalıştırma (Ollama) — **Faz 2: orkestrasyon/istemci katmanı hazır, model indirme onay bekliyor** |
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

`hardware-probe/` Faz 2'de ilk implementasyonunu aldı (Python, stdlib-only,
20 test). `local-runtime/` de Faz 2'de orkestrasyon/istemci katmanını aldı
(tier→model önerisi, Ollama REST istemcisi, 15 test) — Ollama kurulumu ve
gerçek model indirme ayrı bir onay bekliyor. `mcp-tools`, `router`,
`cloud-bridge` hâlâ Faz 1 placeholder aşamasında.
