# ai-stack/

Navigator'ı "AI-native" yapan katman. Yapay zekayı üçüncü parti bir uygulama
olarak değil, işletim sisteminin doğal bir parçası olarak sunmayı hedefler.

Beş bileşenden oluşur, her biri kendi README'sinde detaylandırılmıştır:

| Modül | Sorumluluk |
|---|---|
| [`hardware-probe/`](hardware-probe/README.md) | Donanımı tespit eder, model tier'ını belirler — **Faz 2: ilk implementasyon hazır** |
| [`local-runtime/`](local-runtime/README.md) | Yerel model çalıştırma (Ollama) — **Faz 2: uçtan uca çalışıyor** (Ollama + `llama3.2:3b` kurulu) |
| [`mcp-tools/`](mcp-tools/README.md) | MCP tabanlı sistem/araç erişimi — **Faz 2: sunucu (stdio + HTTP+SSE) + salt-okunur dosya sistemi araçları hazır** |
| [`router/`](router/README.md) | Yerel↔bulut hibrit istek yönlendirme — **Faz 2: her iki yol da uçtan uca gerçek** |
| [`cloud-bridge/`](cloud-bridge/README.md) | Bulut model sağlayıcılarına bağlantı (Anthropic Claude API) — **Faz 2: kimlik bilgisi/istemci katmanı hazır, router'a bağlı** |

## Veri akışı (Faz 2'de gerçek kod — sadece niyet değil)

```
kullanıcı isteği (shell/ asistan paneli)
        │
        ▼
    router/  ──► hardware-probe/ (tier kararı)
        │
        ├──► local-runtime/  (yerel model yeterliyse) — GERÇEKTEN ÇALIŞIYOR
        │
        └──► cloud-bridge/   (yerel yetersiz/kullanıcı tercih ederse)
                     │
                     ▼
              mcp-tools/ (her iki yolda da araç çağrıları için ortak katman)
```

## Durum

Beş modülün tamamı Faz 2'de en az bir implementasyon aşamasına ulaştı.
`router` her iki yolu da (`local` ve `cloud`) gerçek subprocess
çağrılarıyla sürüyor, ve **yerel yol artık bu makinede tamamen gerçek**:
Ollama kuruldu (`curl -fsSL https://ollama.com/install.sh | sh`, ~1.37 GB)
ve önerilen model indirildi (`ollama pull llama3.2:3b`, ~2 GB) — basit
istekler gerçekten yerel LLM'de üretiliyor.

- `hardware-probe/` — ilk implementasyon tamamlandı (Python, stdlib-only, 20 test)
- `local-runtime/` — **uçtan uca çalışıyor**: `ollama_available: true`,
  `model_ready: true`, gerçek `generate()` çağrıları başarılı (tier→model
  önerisi, Ollama REST istemcisi, 16 test)
- `router/` — karar katmanı + **local-runtime ve cloud-bridge entegrasyonu**
  tam çalışıyor (`route` kararına göre ilgili modülü gerçekten çağırıyor ve
  gerçek sonuç alıyor, 26 test)
- `mcp-tools/` — MCP sunucusu (resmi SDK kurmadan, stdlib-only; **iki
  transport**: stdio ve HTTP+SSE — ikisi de gerçek subprocess/TCP
  soketleriyle test edildi) VE salt-okunur, sandbox'lı dosya sistemi
  araçları (`read_file`, `list_directory` — path traversal engellemesi
  test edildi) hazır; 41 test, `route_request` artık gerçek yerel üretimi
  de miras alıyor
- `cloud-bridge/` — kimlik bilgisi/istemci katmanı hazır (Anthropic Claude
  API, ham HTTP; 15 test) — **`router`'a bağlı**; gerçek bir API çağrısı
  henüz yapılmadı/test edilmedi (kimlik bilgisi yok, `router` karmaşık
  isteklerde buraya gerçekten düşüyor ama "unavailable" ile sonuçlanıyor)

Beş modülün dördü (`hardware-probe` → `local-runtime` → `router` →
`mcp-tools`) gerçek MCP protokolü/subprocess zinciriyle çalışıyor.
`router → local-runtime` zinciri artık **gerçek bir yerel LLM yanıtı**
üretiyor (mock değil); `router → cloud-bridge` zinciri de gerçek çalışıyor
ama Claude API kimlik bilgisi olmadığından "unavailable" ile sonuçlanıyor.