# ai-stack/assistant/

## Ne yapıyor

Navigator'ın **Faz 4** hedefi olan "uçtan uca asistan paneli deneyimi"nin
ilk somut adımı: `router`, `mcp-tools`, `local-runtime` ve `cloud-bridge`'i
tek bir gerçek konuşma döngüsünde birleştiren bir CLI/REPL. Bu, tasarım
ilkelerindeki "her şey keşfedilebilir olmalı" ilkesinin ilk gerçek kanıtı —
kullanıcı "bu makinede kaç çekirdek var?" gibi bir soruyu web'de aramak
yerine doğrudan sorabilir ve **gerçek bir araç çağrısıyla** doğru cevabı
alır (bkz. `docs/architecture.md` "Tasarım ilkeleri").

Quickshell/Hyprland UI'ı bu makinede test edilemediğinden (bkz.
`shell/README.md`, `ai-stack/mcp-tools/README.md`), Faz 4'e **UI'ı
beklemeden**, bu makinede gerçekten çalıştırılıp test edilebilecek bir
terminal deneyimiyle başlandı.

## Mimari

```
kullanıcı promptu
      │
      ▼
router --decide-only  ──►  hardware-probe (tier kararı)
      │
      ├── route: "local" ──► local-runtime --converse (tool-use döngüsü, KISITLI araç seti)
      │
      └── route: "cloud" ──► cloud-bridge --converse (tool-use döngüsü, TAM araç seti)
                                    │         ▲
                                    ▼         │
                              mcp-tools (gerçek araç çağrısı — MCP stdio)
```

Hem `local` hem `cloud` rotası GERÇEK bir tool-use döngüsü kurar — ikisi
de mcp-tools'un araçlarını gerçekten çağırabilir. Fark, hangi araçlara
erişebildikleri ve güvenilirlikleri (aşağıya bkz. "Yerel tool-use").

- **`router --decide-only`**: router'a eklenen bir bayrak — sadece route
  kararını (`complexity`/`hardware_tier`/`model_ready`/`route`/
  `reasoning`) döner, `local-runtime` veya `cloud-bridge`'i ÇALIŞTIRMAZ.
  Bunun nedeni: assistant kendi üretim akışını (tool-use döngüsünü) kurmak
  zorunda, router'ın kendi tek seferlik çağrısını yapıp sonucu atmak hem
  israf hem de gereksiz bir gerçek API/model çağrısı olurdu.
- **`cloud_bridge --converse`**: cloud-bridge'in CLI'ına eklenen bir mod —
  stdin'den tam bir mesaj listesi + `tools` şeması (Claude formatı) alır,
  Claude API'nin HAM yanıtını (`tool_use` blokları, `stop_reason` dahil)
  stdout'a basar.
- **`local_runtime --converse`**: local-runtime'ın CLI'ına eklenen bir mod
  — stdin'den tam bir mesaj listesi + `tools` şeması (OpenAI-benzeri
  format) alır, Ollama `/api/chat`'in HAM yanıtını (`tool_calls` dahil)
  stdout'a basar.
- **`mcp_client.py`**: mcp-tools'a karşı gerçek bir MCP istemcisi.
  Diğer ai-stack modüllerinin "tek seferlik subprocess" deseninden farklı
  olarak (`python3 -m X --prompt ...`, süreç bitince JSON okunur) burada
  **kalıcı bir oturum** var — `initialize` bir kez yapılır, sonra aynı
  süreç üzerinden birden çok `tools/call` isteği gönderilir (MCP
  protokolünün gerektirdiği gibi).
- **`conversation.py`**: `run_turn()` — router kararına göre
  `run_cloud_turn()` (Claude tool-use döngüsü, tam araç seti) veya
  `run_local_turn()`'e (Ollama tool-use döngüsü, kısıtlı araç seti) dağıtır.

## Konuşma geçmişi / hafıza

Her iki yol da aynı düz `history: [{"role", "content"}, ...]` biçimini
kullanır — sadece kullanıcı/asistan METİN turları (ne Claude'un
tool_use/tool_result blokları ne Ollama'nın tool_calls'ı geçmişe dahil
edilir, sadece o turun içinde kalır). Bu, bir konuşma içinde route değişse
bile (önce local, sonra cloud) geçmişin taşınabilir kalmasını sağlar —
ikisi de Claude/Ollama'nın native `{"role", "content"}` mesaj formatına
doğrudan uyuyor.

Geçmiş `MAX_HISTORY_MESSAGES` (20 mesaj, ~10 tur) ile kırpılır — sınırsız
büyümeyi ve gereksiz yere büyüyen prompt/API maliyetini önler.

**Nerede tutulur:**
- REPL'de otomatik olarak bellekte (oturum boyunca), `/reset` ile temizlenir.
- `--history-file <yol>` verilirse bir JSON dosyasında KALICI tutulur —
  hem `--prompt` hem REPL modunda, her turdan sonra dosyaya yazılır (bir
  çökme geçmişi kaybetmesin diye) — **ayrı süreçler arasında bile hafıza**.

## `run_cloud_turn()` — gerçek tool-use döngüsü (tam araç seti)

1. `mcp_client.list_tools()` ile mcp-tools'un 10 aracının şeması alınır,
   Claude'un `tools` formatına çevrilir (`inputSchema` → `input_schema`).
2. Claude'a mesaj gönderilir. Yanıt `stop_reason: "tool_use"` ise, her
   `tool_use` bloğu **gerçekten** `mcp_client.call_tool()` ile çalıştırılır
   (mock değil — gerçek `hardware_tier`, `read_file`, `list_windows` vb.,
   `write_file`/`delete_file`/`rename_file` dahil).
3. Sonuç `tool_result` mesajı olarak geri beslenir, Claude tekrar çağrılır.
4. Claude `tool_use` dışında bir `stop_reason` verene kadar (en fazla 8 tur
   — sonsuz döngü koruması) tekrarlanır, son metin döner.

Gerçek bir çalıştırma örneği (bu makinede, gerçek Claude API + gerçek
mcp-tools ile):

```
$ python3 -m assistant --prompt "Bu makinede kaç tane CPU çekirdeği var, toplam RAM ne kadar, ve ayrık bir grafik kartı var mı yok mu, ... gerçek donanım tespit aracını kullanarak öğren ..." --pretty
{
  "status": "ok",
  "content": "Donanım tespit aracının döndürdüğü gerçek verilere göre:\n\n- CPU çekirdeği: 6 fiziksel / 6 mantıksal (Intel i5-8500 @ 3.00GHz)\n- Toplam RAM: ~15.4 GB\n- Ayrık grafik kartı: Yok, yalnızca tümleşik Intel GPU var",
  "tool_calls": [{"name": "hardware_tier", "input": {}}],
  "route": "cloud",
  "hardware_tier": "low",
  "reasoning": "karmaşık istek + düşük donanım tier'ı: yerel model yetersiz kalabilir"
}
```

Tüm sayılar gerçek ve doğru (bu makinenin gerçek donanımıyla eşleşiyor).

## `run_local_turn()` — yerel tool-use (kısıtlı araç seti, bilinen güvenilirlik sınırlaması)

Ollama `/api/chat` ile aynı desende bir tool-use döngüsü kurar — ama gerçek
testte `llama3.2:3b`'nin (3B parametreli, cloud'daki Claude'dan çok daha
küçük) davranışı **belirgin şekilde daha az güvenilir** çıktı. Bu, kod
hatası değil, küçük modellerin bilinen, dokümante edilmiş bir sınırlaması —
"gerçek olmayan hiçbir şey başarılı gösterilmez" ilkesi gereği burada
dürüstçe kayıtlı:

### Gerçekte gözlenen sorunlar ve gerçek düzeltmeler

1. **Halüsinasyon argümanlar.** Sıfır-parametreli `hardware_tier` aracına
   bile `{"path": "/home/chief"}` veya `{"": "null"}` gibi uydurma
   argümanlar üretti. **Düzeltme:** her araç çağrısının argümanları,
   aracın gerçek `inputSchema`'sındaki `properties` anahtarlarına göre
   filtreleniyor — şemada olmayan her anahtar atılıyor.

2. **Güvenlik riski — halüsinasyon yazma çağrısı.** Zararsız bir "sadece
   'merhaba' de" isteğinde bile kendiliğinden `write_file`'ı
   `overwrite: true` ile çağırmaya kalkıştı (hedef `/home/chief` bir dizin
   olduğu için mcp-tools katmanında hata verip başarısız oldu — ama başka
   bir yolda gerçekten dosya değiştirebilirdi). Bu, "sistemi değiştiren
   her eylem açık onay ister" ilkesinin gerçek bir ihlal riskiydi.
   **Düzeltme:** `write_file`/`delete_file`/`rename_file` yerel modele HİÇ
   gösterilmiyor (`LOCAL_SAFE_TOOL_NAMES` — sadece salt-okunur araçlar:
   `hardware_tier`, `route_request`, `read_file`, `list_directory`,
   `list_windows`, `list_workspaces`, `active_window`). Model yine de
   halüsinasyonla gösterilmeyen bir aracı çağırırsa, savunma katmanı
   `mcp_client.call_tool()`'a hiç ulaşmadan reddeder — gerçek testte hem
   "hiç gösterilmez" hem "gösterilmese de reddedilir" doğrulandı.

3. **Hafıza + tool-use birlikte kararsızlık.** Sistem promptu olmadan,
   model basit bir hafıza sorusunda ("Benim adım neydi?") bile gereksiz
   araç çağırmaya kalkışıp bazen yapılandırılmış `tool_calls` yerine ham
   JSON metnini düz cevap olarak yazdı. **Düzeltme:** cloud ile aynı
   `SYSTEM_PROMPT` artık local'e de veriliyor, ayrıca "önceki konuşmadan
   bir şey soruluyorsa araç kullanma" talimatı eklendi — gerçek testte
   güvenilirliği belirgin arttırdı ama **tam olarak sıfırlamadı**
   (aşağıya bkz.).

### Kalan, kabul edilen gerçek sınırlama

Yukarıdaki düzeltmelerden sonra bile, 3B model ara sıra (i) gereksiz yere
salt-okunur bir araç çağırabiliyor (zararsız, ama gereksiz) veya (ii)
yapılandırılmış `tool_calls` yerine tool-call-şekilli ham JSON metni
üretebiliyor (o turda araç hiç çalıştırılamaz, model kendi kendine
"cevap" gibi görünen ama işe yaramaz bir metin yazar). Bu, **modelin
kendisinin doğal değişkenliği** — 8B+ modellerde veya cloud'da (Claude)
gözlenmedi. Gerçek test suite'i bu yüzden içerik-kalitesine bağlı
senaryolarda sınırlı sayıda tekrar dener (bkz.
`tests/test_integration.py` `_run_cli_until`) — güvenlik testleri
(yazma aracı asla gösterilmez/çalıştırılmaz) DETERMİNİSTİK kaldığından
bunu kullanmaz.

Gerçek, başarılı bir çalıştırma örneği (düzeltmelerden sonra, bu makinede):

```
$ python3 -m assistant --prompt "Bu makinede kaç CPU çekirdeği var? Aracı kullanarak öğren, kısa cevap ver."
{"content": "Bu makinenin 6 CPU çekirdeği vardır.", "tool_calls": [{"name": "hardware_tier", "input": {}}], "route": "local", ...}
```

Bu, ilk implementasyonda (düzeltmelerden ÖNCE) tam olarak başarısız olan
senaryoydu (`"Lütfen makine modelini veya aracinızı girin..."` gibi
alakasız bir halüsinasyon üretmişti) — artık gerçek, doğru veriyle
cevaplıyor.

## Kullanım

Harici bağımlılık yok, sadece Python 3.11+ (stdlib). `router`, `mcp-tools`,
`local-runtime`, `cloud-bridge`'in yanında (kardeş dizinler olarak)
bulunması gerekiyor.

Tek seferlik (JSON çıktı, test/scripting için):

```sh
cd ai-stack/assistant
python3 -m assistant --prompt "..." [--prefer balanced|privacy|cost|speed] [--pretty]
```

İnteraktif REPL (varsayılan, insan diliyle çıktı, geçmiş otomatik bellekte):

```sh
cd ai-stack/assistant
python3 -m assistant
> Bu makinede kaç çekirdek var?
...
> /reset   # konuşma geçmişini sıfırlar
> çıkış
```

Kalıcı geçmiş (ayrı çalıştırmalar/süreçler arasında da hatırlar):

```sh
python3 -m assistant --prompt "..." --history-file ~/.navigator-assistant-history.json
```

Bulut yolu için gerçek bir Claude API key gerekir — bkz.
`ai-stack/cloud-bridge/README.md` "Kimlik bilgisini yerel olarak bağlamak".
Yerel yol (Ollama) her zaman çalışır, kimlik bilgisi gerekmez.

Testler:

```sh
cd ai-stack/assistant
python3 -m unittest discover -v -s tests
```

## Kapsam dışı — henüz yapılmadı

- Yerel yolun güvenilirliği tam değil (yukarıya bkz.) — bu, model boyutu
  kaynaklı bir sınırlama, daha büyük bir yerel model veya prompt
  mühendisliğinin ötesinde bir çözüm gerektirebilir.
- Gerçek bir Quickshell/Hyprland UI'a bağlı değil — bu, ertelenen gerçek
  compositor testine bağlı (bkz. `ai-stack/mcp-tools/README.md`).
- Router'ın karmaşıklık sezgisi "araç gerekebilir mi" sinyalini
  kullanmıyor — kısa istekler yerele düşüyor, karmaşık olanlar buluta.
- Streaming yok — her yanıt tek seferde, tam olarak döner.

## Durum

Faz 4 — `router` (`--decide-only`), `cloud-bridge` (`--converse`,
`send_messages()`), `local-runtime` (`--converse`, `chat()`) ve yeni
`assistant` modülü (`mcp_client.py`, `conversation.py`, CLI/REPL)
tamamlandı. **Hem cloud hem local yolu artık gerçek bir tool-use
döngüsüyle çalışıyor** — cloud tam araç setiyle ve güvenilir, local
kısıtlı (salt-okunur) araç setiyle ve gerçek testte belgelenen bir
güvenilirlik sınırlamasıyla (yukarıya bkz.). Konuşma geçmişi/hafıza
eklendi — REPL'de bellekte, `--history-file` ile ayrı süreçler arasında
bile kalıcı. Gerçek uçtan uca doğrulandı: gerçek Claude API + gerçek
Ollama + gerçek mcp-tools ile, ikisi de gerçek araç çağırıyor, ikisi de
dürüstçe belgelendi (özellikle yerel yolda gerçek testte yakalanan bir
güvenlik riski — halüsinasyon `write_file` çağrısı — gerçekten
düzeltildi, araç erişimi kısıtlanarak).

40 test geçiyor (27 mock'lanmış conversation testi, 7 mock'lanmış MCP
istemci testi, 6 gerçek entegrasyon testi — dördü her zaman çalışır
[yerel tool-use, güvenlik, hafıza], ikisi kimlik bilgisi varsa gerçek
Claude API'ye karşı çalışır, yoksa otomatik `skip`).
