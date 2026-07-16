# ai-stack/

Navigator'ı "AI-native" yapan katman. Yapay zekayı üçüncü parti bir uygulama
olarak değil, işletim sisteminin doğal bir parçası olarak sunmayı hedefler.

Altı bileşenden oluşur, her biri kendi README'sinde detaylandırılmıştır:

| Modül | Sorumluluk |
|---|---|
| [`hardware-probe/`](hardware-probe/README.md) | Donanımı tespit eder, model tier'ını belirler — **gerçek donanımda doğrulandı** |
| [`local-runtime/`](local-runtime/README.md) | Yerel model çalıştırma (Ollama) — **uçtan uca çalışıyor**, tool-calling destekli (Ollama + `llama3.2:3b` kurulu) |
| [`mcp-tools/`](mcp-tools/README.md) | MCP tabanlı sistem/araç erişimi — **10 araç, iki transport (stdio + HTTP+SSE), gerçek test edildi** |
| [`router/`](router/README.md) | Yerel↔bulut hibrit istek yönlendirme — **her iki yol da uçtan uca gerçek** |
| [`cloud-bridge/`](cloud-bridge/README.md) | Bulut model sağlayıcısı (Anthropic Claude API) — **gerçek kimlik bilgisi bağlı, tool-use destekli** |
| [`assistant/`](assistant/README.md) | Faz 4: yukarıdaki beşini tek bir gerçek konuşma döngüsünde birleştiren CLI/REPL — **hem cloud hem local'de gerçek tool-use döngüsü + kalıcı konuşma geçmişi** |

## Veri akışı (gerçek kod — sadece niyet değil)

```
kullanıcı promptu (assistant/ CLI veya REPL)
        │
        ▼
router --decide-only  ──►  hardware-probe/ (tier kararı)
        │
        ├── route: "local" ──► local-runtime/ --converse (tool-use, KISITLI araç seti)
        │
        └── route: "cloud" ──► cloud-bridge/ --converse (tool-use, TAM araç seti)
                                      │            ▲
                                      ▼            │
                                mcp-tools/ (gerçek araç çağrısı — MCP stdio)
```

`shell/` (Quickshell UI) bu zincire henüz bağlı değil — bu makinede
Hyprland/Quickshell gerçek test edilemediğinden (bkz. `shell/README.md`),
Faz 4 UI'ı beklemeden bu terminal deneyimiyle başladı.

## Durum

Altı modülün tamamı gerçek ve bu makinede gerçek verilerle test edildi
(mock/placeholder değil):

- **`hardware-probe/`** — gerçek donanımda doğrulandı: bu makinede
  tier="low" (Intel i5-8500, 6 çekirdek, 15.4 GB RAM, ayrık GPU yok), 20 test.
- **`local-runtime/`** — Ollama kuruldu ve `llama3.2:3b` indirildi;
  `model_ready: true`, gerçek `generate()` çağrıları başarılı. Faz 4'te
  `chat()`/`--converse` eklendi — gerçek testte tool-calling doğrulandı,
  20 test.
- **`router/`** — karar katmanı + local-runtime/cloud-bridge entegrasyonu;
  Faz 4'te eklenen `--decide-only` sadece karar üretir, çalıştırmaz
  (assistant'ın kendi üretim akışını kurabilmesi için), 30 test.
- **`mcp-tools/`** — MCP sunucusu (resmi SDK kurmadan, stdlib-only; iki
  transport, Bearer token kimlik doğrulamalı HTTP+SSE) VE 10 araç
  (sandbox'lı dosya sistemi araçları + salt-okunur Hyprland sorgu
  araçları), 88 test.
- **`cloud-bridge/`** — gerçek bir Claude API key bağlandı (`.env.local`,
  gitignore'lı); Faz 4'te çok turlu mesaj + tool-use desteği eklendi
  (`send_messages()`, `--converse`), 20 test.
- **`assistant/`** — Faz 4'ün ilk adımı: yukarıdaki beşini birleştiren
  gerçek bir konuşma döngüsü. **Hem cloud hem local yolu artık gerçek bir
  tool-use döngüsüyle çalışıyor** — örn. "bu makinede kaç çekirdek var?"
  sorusuna `hardware_tier` aracını gerçekten çalıştırıp doğru cevap
  veriyor (ikisinde de). Gerçek testte yerel yolda ciddi bir güvenlik
  riski yakalandı (3B model zararsız bir istekte bile kendiliğinden
  `write_file`'ı `overwrite=true` ile çağırmaya kalkıştı) ve gerçekten
  düzeltildi — yazma/silme araçları yerel modele hiç gösterilmiyor, sadece
  salt-okunur erişimi var. Bu ve diğer gerçek güvenilirlik bulguları
  gizlenmeden belgelendi (bkz. `assistant/README.md`). Konuşma
  geçmişi/hafıza eklendi — REPL'de bellekte, `--history-file` ile ayrı
  süreçler arasında bile kalıcı. 40 test.

Toplam ~218 test, ai-stack genelinde. Gerçek entegrasyon testlerinin
büyük kısmı gerçek subprocess/TCP/dosya sistemi/Ollama/Claude API
üzerinden çalışıyor; kimlik bilgisi gerektirenler `.env.local` yoksa
(CI dahil) otomatik `skip` olacak şekilde tasarlandı.
