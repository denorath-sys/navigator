# ai-stack/assistant/

## Ne yapıyor

Navigator'ın **Faz 4** hedefi olan "uçtan uca asistan paneli deneyimi"nin
ilk somut adımı: `router`, `mcp-tools` ve `cloud-bridge`'i tek bir gerçek
konuşma döngüsünde birleştiren bir CLI/REPL. Bu, tasarım ilkelerindeki
"her şey keşfedilebilir olmalı" ilkesinin ilk gerçek kanıtı — kullanıcı
"bu makinede kaç çekirdek var?" gibi bir soruyu web'de aramak yerine
doğrudan sorabilir ve **gerçek bir araç çağrısıyla** doğru cevabı alır
(bkz. `docs/architecture.md` "Tasarım ilkeleri").

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
      ├── route: "local" ──► local-runtime  (DÜZ ÜRETİM, araç kullanımı YOK)
      │
      └── route: "cloud" ──► cloud-bridge --converse (tool-use döngüsü)
                                    │         ▲
                                    ▼         │
                              mcp-tools (gerçek araç çağrısı — MCP stdio)
```

- **`router --decide-only`** (yeni): router'a eklenen bir bayrak — sadece
  route kararını (`complexity`/`hardware_tier`/`model_ready`/`route`/
  `reasoning`) döner, `local-runtime` veya `cloud-bridge`'i ÇALIŞTIRMAZ.
  Bunun nedeni: assistant kendi üretim akışını (özellikle bulut yolunda
  tool-use döngüsünü) kurmak zorunda, router'ın kendi (tool'suz) tek
  seferlik `generate()` çağrısını yapıp sonucu atmak hem israf hem de
  gereksiz bir gerçek API çağrısı olurdu.
- **`cloud_bridge --converse`** (yeni): cloud-bridge'in CLI'ına eklenen
  bir mod — stdin'den tam bir mesaj listesi + `tools` şeması alır, Claude
  API'nin HAM yanıtını (`tool_use` blokları, `stop_reason` dahil) stdout'a
  basar. Mevcut `--prompt` modu (basitleştirilmiş tek turlu rapor)
  korunuyor, `--converse` ayrı ve ek bir mod.
- **`mcp_client.py`**: mcp-tools'a karşı gerçek bir MCP istemcisi.
  Diğer ai-stack modüllerinin "tek seferlik subprocess" deseninden farklı
  olarak (`python3 -m X --prompt ...`, süreç bitince JSON okunur) burada
  **kalıcı bir oturum** var — `initialize` bir kez yapılır, sonra aynı
  süreç üzerinden birden çok `tools/call` isteği gönderilir (MCP
  protokolünün gerektirdiği gibi).
- **`conversation.py`**: `run_turn()` — router kararına göre `run_cloud_turn()`
  (Claude tool-use döngüsü) veya `run_local_turn()`'e (düz üretim) dağıtır.

## `run_cloud_turn()` — gerçek tool-use döngüsü

1. `mcp_client.list_tools()` ile mcp-tools'un 10 aracının şeması alınır,
   Claude'un `tools` formatına çevrilir (`inputSchema` → `input_schema`).
2. Claude'a mesaj gönderilir. Yanıt `stop_reason: "tool_use"` ise, her
   `tool_use` bloğu **gerçekten** `mcp_client.call_tool()` ile çalıştırılır
   (mock değil — gerçek `hardware_tier`, `read_file`, `list_windows` vb.).
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

## Bilinen ve önemli sınırlama — yerel yolda araç kullanımı YOK

`run_local_turn()` düz üretim yapar, **tool-use içermez**. Ollama'nın
function-calling desteği bu istemcide henüz implemente edilmedi. Bu,
gerçek testte açıkça ortaya çıktı — kısa/basit bir soru (`router`'ın
karmaşıklık sezgisi yüzünden) yerele düşer ve model gerçek veriye
erişemediği için ya genel bir cevap ya da (gözlemlenen gerçek örnek)
alakasız bir halüsinasyon üretir:

```
$ python3 -m assistant --prompt "Bu makinede kaç CPU çekirdeği var? Aracı kullanarak öğren."
{"content": "Lütfen makine modelini veya aracinızı girin...", "route": "local", "tool_calls": []}
```

Bu, tasarım ilkelerindeki "gerçek olmayan hiçbir şey başarılı gösterilmez"
ilkesi gereği gizlenmiyor — gerçek bir sınırlama olarak burada kayıtlı.
Ayrıca `router/decision.py`'nin karmaşıklık sezgisi (kelime sayısı) şu an
"bu soru araç gerektirir mi" bilgisini hiç kullanmıyor — bu, `decision.py`
docstring'inde zaten "Faz 3+'ta ele alınacak" olarak not edilmişti, burada
gerçek bir örnekle doğrulandı. Olası düzeltmeler (ileride): yerel modele
de tool-use eklemek, veya router'ın karmaşıklık tahminine "araç gerekebilir
mi" sinyalini eklemek.

## Kullanım

Harici bağımlılık yok, sadece Python 3.11+ (stdlib). `router`, `mcp-tools`,
`local-runtime`, `cloud-bridge`'in yanında (kardeş dizinler olarak)
bulunması gerekiyor.

Tek seferlik (JSON çıktı, test/scripting için):

```sh
cd ai-stack/assistant
python3 -m assistant --prompt "..." [--prefer balanced|privacy|cost|speed] [--pretty]
```

İnteraktif REPL (varsayılan, insan diliyle çıktı):

```sh
cd ai-stack/assistant
python3 -m assistant
> Bu makinede kaç çekirdek var?
...
> çıkış
```

Bulut yolu ve tool-use için gerçek bir Claude API key gerekir — bkz.
`ai-stack/cloud-bridge/README.md` "Kimlik bilgisini yerel olarak bağlamak".

Testler:

```sh
cd ai-stack/assistant
python3 -m unittest discover -v -s tests
```

## Kapsam dışı — henüz yapılmadı

- Yerel yolda tool-use yok (yukarıya bkz.).
- Konuşma geçmişi/hafızası yok — her `run_turn()` çağrısı bağımsız, çok
  turlu bir kullanıcı konuşması (önceki turları hatırlama) henüz yok.
- Gerçek bir Quickshell/Hyprland UI'a bağlı değil — bu, ertelenen gerçek
  compositor testine bağlı (bkz. `ai-stack/mcp-tools/README.md`).
- Router'ın karmaşıklık sezgisi "araç gerekebilir mi" sinyalini
  kullanmıyor (yukarıya bkz.).
- Streaming yok — her yanıt tek seferde, tam olarak döner.

## Durum

Faz 4'ün ilk adımı — `router` (`--decide-only`), `cloud-bridge`
(`--converse`, `send_messages()`) ve yeni `assistant` modülü
(`mcp_client.py`, `conversation.py`, CLI/REPL) tamamlandı. Gerçek uçtan
uca doğrulandı: gerçek Claude API + gerçek mcp-tools + gerçek Ollama ile,
hem tool-use'lu bulut yolu hem araçsız yerel yolu (ikisi de gerçek, ikisi
de dürüstçe belgelendi). 23 test geçiyor (13 mock'lanmış conversation
testi, 7 mock'lanmış MCP istemci testi, 3 gerçek entegrasyon testi —
biri her zaman çalışır [yerel], ikisi kimlik bilgisi varsa gerçek Claude
API'ye karşı çalışır, yoksa otomatik `skip`).
