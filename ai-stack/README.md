# ai-stack/

Navigator'ı "AI-native" yapan katman. Yapay zekayı üçüncü parti bir uygulama
olarak değil, işletim sisteminin doğal bir parçası olarak sunmayı hedefler.

Beş bileşenden oluşur, her biri kendi README'sinde detaylandırılmıştır:

| Modül | Sorumluluk |
|---|---|
| [`hardware-probe/`](hardware-probe/README.md) | Donanımı tespit eder, model tier'ını belirler — **Faz 2: ilk implementasyon hazır** |
| [`local-runtime/`](local-runtime/README.md) | Yerel model çalıştırma (Ollama) — **Faz 2: orkestrasyon/istemci katmanı hazır, model indirme onay bekliyor** |
| [`mcp-tools/`](mcp-tools/README.md) | MCP tabanlı sistem/araç erişimi — **Faz 2: ilk MCP sunucusu hazır** |
| [`router/`](router/README.md) | Yerel↔bulut hibrit istek yönlendirme — **Faz 2: karar katmanı + cloud-bridge entegrasyonu hazır** |
| [`cloud-bridge/`](cloud-bridge/README.md) | Bulut model sağlayıcılarına bağlantı (Anthropic Claude API) — **Faz 2: kimlik bilgisi/istemci katmanı hazır, router'a bağlı** |

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

Beş modülün tamamı Faz 2'de en az bir implementasyon aşamasına ulaştı ve
`router` artık her iki yolu (`local`/`cloud`) gerçek subprocess çağrılarıyla
sürüyor:

- `hardware-probe/` — ilk implementasyon tamamlandı (Python, stdlib-only, 20 test)
- `local-runtime/` — orkestrasyon/istemci katmanı hazır (tier→model önerisi,
  Ollama REST istemcisi, 15 test) — Ollama kurulumu ve model indirme ayrı bir
  onay bekliyor; `generate()` henüz `router`'a bağlanmadı
- `router/` — karar katmanı + **cloud-bridge entegrasyonu** hazır (yerel/bulut
  yönlendirme mantığı, `route: "cloud"` kararında gerçekten `cloud-bridge`'i
  çağırıyor, 21 test)
- `mcp-tools/` — ilk MCP sunucusu hazır (resmi SDK kurmadan, stdlib-only
  JSON-RPC 2.0 stdio transport; `hardware_tier` ve `route_request` araçları, 16 test)
- `cloud-bridge/` — kimlik bilgisi/istemci katmanı hazır (Anthropic Claude
  API, ham HTTP; 15 test) — **`router`'a bağlı**; gerçek bir API çağrısı
  henüz yapılmadı/test edilmedi (kimlik bilgisi yok)

Beş modülün dördü (`hardware-probe` → `local-runtime` → `router` →
`mcp-tools`) gerçek MCP protokolü/subprocess zinciriyle, `router` →
`cloud-bridge` de ayrıca gerçek subprocess zinciriyle uçtan uca çalışıyor —
ikisi de bu makinede doğrulandı (kimlik bilgisi/model olmadan graceful
"unavailable" durumları dahil).
