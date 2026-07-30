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

`shell/` (Quickshell UI) bu zincire Faz 4'te gerçekten bağlandı:
`shell/AssistantPanel.qml` `router`'ı subprocess olarak çağırıyor ve bu
gerçek bir CI VM'inde uçtan uca doğrulandı (bkz. `shell/README.md`).

## İmajdaki kurulum yolu

`image/Containerfile` **Katman 5**, bu altı modülü Navigator imajına
gerçekten katmanlıyor:

```
/usr/share/navigator/ai-stack/
├── hardware-probe/{hardware_probe/,pyproject.toml}
├── local-runtime/{local_runtime/,pyproject.toml}
├── cloud-bridge/{cloud_bridge/,pyproject.toml}
├── mcp-tools/{mcp_tools/,pyproject.toml}
├── router/{router/,pyproject.toml}
└── assistant/{assistant/,pyproject.toml}
```

**Düz kardeş hiyerarşi bir çalışma zamanı sözleşmesidir, tercih değil.**
Modüller birbirini `python3 -m <modül>` subprocess'i olarak, cwd'ye
göreli kardeş yollarla çağırıyor (`router` → `../local-runtime`,
`../cloud-bridge`; `local-runtime` → `../hardware-probe`; `assistant` →
`../router`, `../mcp-tools`). Dizin adları repodaki adlarla birebir aynı
olmak zorunda; aksi halde zincir sessizce kırılır — gerçek bir CI
denemesinde tam olarak bu yaşandı (`hardware-probe` kopyalanmamıştı,
`router` boş stdout döndürdü).

İmaja **sadece çalışma zamanı kodu** giriyor: paket dizini +
`pyproject.toml`. `tests/` girmiyor. `.env.local` de girmiyor — kimlik
bilgisi imaja gömülmez (aşağıya bkz.). Altı modülün hiçbirinin üçüncü
parti bağımlılığı olmadığı için (`dependencies = []`, stdlib-only) bu
katman pip/venv kurmuyor; tek çalışma zamanı bağımlılığı python3 ≥ 3.11
ve bu build sırasında iddia ediliyor.

### Salt-okunur `/usr` ve bytecode

Navigator bir ostree/bootc imajı: çalışan sistemde `/usr` salt-okunur.
Python bu yüzden `__pycache__`'i çalışma zamanında yazamaz ve her
çağrıda kaynağı yeniden derler — bu zincirde tek istek 3-4 subprocess
demek olduğu için ölçülebilir bir maliyet. Bytecode bu yüzden build
sırasında üretiliyor:

```
python3 -m compileall -q --invalidation-mode checked-hash <yol>
```

`checked-hash` bilinçli bir seçim ve gerçekten test edildi: ostree
commit tüm dosya `mtime`'larını normalize ediyor, dolayısıyla
varsayılan timestamp tabanlı geçersizleştirmeyle .pyc'ler bayat sayılır.
Yerel bir deneyde (mtime'lar 1970'e çekilip dizin salt-okunur yapılarak)
`python3 -v` çıktısı bunu doğruladı:

- timestamp modu → `# bytecode is stale for 'hardware_probe'` +
  `could not create ... PermissionError` (her çağrıda yeniden derleme,
  cache yazılamıyor)
- `checked-hash` → `# ...probe.cpython-313.pyc matches ...probe.py`
  (hash tabanlı doğrulama mtime'dan bağımsız, .pyc kullanılıyor)

### Kimlik bilgisi (bilinen sınırlama)

`cloud-bridge` kimlik bilgisini **sadece** `ANTHROPIC_API_KEY` /
`ANTHROPIC_AUTH_TOKEN` ortam değişkenlerinden okuyor (koda gömülü
dosya okuma yok — `cloud_bridge/client.py`). Geliştirmede kullanılan
`.env.local` yalnızca elle `source` edilen bir kolaylık ve imaja
girmiyor. Sonuç: gerçek imajda kullanıcının kimlik bilgisini kendi
oturum ortamına koyması gerekiyor; `/usr` salt-okunur olduğu için
`/usr/share/navigator/ai-stack/cloud-bridge/.env.local` gibi bir dosya
oluşturulamaz da. Kullanıcı seviyesinde bir yapılandırma yolu (ör.
`~/.config/navigator/env` okuyan bir katman) henüz tasarlanmadı —
`shell/AssistantPanel.qml`'in başlattığı `Process` Quickshell'in
ortamını miras aldığından, o ortamda değişken yoksa yanıt
`[cloud] unavailable: credentials_not_configured` olur.

### Ollama (Katman 6, hâlâ PLACEHOLDER)

Yerel model runtime'ının kendisi (Ollama/llama.cpp ikilileri) boyut
kısıtı nedeniyle hâlâ imaja girmiyor. `local-runtime` bunu gerektirmiyor:
Ollama yoksa `model_ready: false` döndürüyor ve `router` isteği buluta
yönlendiriyor — CI'da gerçekten doğrulanan yol.

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
  (assistant'ın kendi üretim akışını kurabilmesi için). Karmaşıklık
  sezgisine "araç gerekebilir mi" sinyali eklendi
  (`mentions_tool_keywords()`) — kısa ama donanım/dosya/pencere ile ilgili
  istekler artık düşük tier'da otomatik buluta düşüyor (gerçek testte
  doğrulandı: bu makinede "kaç CPU çekirdeği var?" artık `route: "cloud"`
  alıyor). 37 test.
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

Altı modülün tamamı ayrıca **gerçek Navigator imajının içinde** ve o
imajdan çalıştırılıyor (Containerfile Katman 5; `/usr` salt-okunur
haldeyken CI'da doğrulanıyor — bkz. yukarıdaki "İmajdaki kurulum yolu").

Toplam ~225 test, ai-stack genelinde. Gerçek entegrasyon testlerinin
büyük kısmı gerçek subprocess/TCP/dosya sistemi/Ollama/Claude API
üzerinden çalışıyor; kimlik bilgisi gerektirenler `.env.local` yoksa
(CI dahil) otomatik `skip` olacak şekilde tasarlandı.
