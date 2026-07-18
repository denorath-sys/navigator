# ai-stack/mcp-tools/

## Ne yapıyor

Navigator asistanının sistemle etkileşim kurmasını sağlayan araç katmanı.
[Model Context Protocol (MCP)](https://modelcontextprotocol.io) standardını
kullanarak, hem yerel hem bulut modellerinin aynı araç setine tek bir
arayüzle erişmesini sağlar — `router/` hangi modeli seçtiğinden bağımsız
olarak araç çağrıları bu modül üzerinden yürütülür.

**Mimari karar (Faz 2):** MCP protokolü, resmi `mcp` Python SDK'sı
kurulmadan, stdlib-only implemente edilerek yazıldı — diğer ai-stack
modülleriyle aynı "harici bağımlılık yok" ilkesi korundu. İki transport
destekleniyor, ikisi de aynı `MCPServer.handle_message()` mantığını
paylaşıyor:

- **stdio** (varsayılan) — newline-delimited JSON-RPC 2.0
- **HTTP+SSE** (`--http`) — klasik iki uç noktalı model (`GET /sse` +
  `POST /messages`), `http.server` ile (bkz. "HTTP+SSE transport" aşağıda)

## Araçlar

On araç kayıtlı — ikisi zaten çalışan diğer ai-stack modüllerini
sarmalıyor, beşi sandbox'lı dosya sistemi erişimi, üçü de Hyprland
compositor durumunu salt-okunur sorguluyor:

| Araç | Açıklama |
|---|---|
| `hardware_tier` | `hardware-probe`'u sarmalar — donanım tier'ını ve CPU/RAM/GPU sinyallerini döner |
| `route_request` | `router`'ı sarmalar — bir isteğin yerel mi bulut mu ile karşılanacağına karar verir (artık gerçek yerel üretim/bulut çağrısını da tetikliyor) |
| `read_file` | Bir dosyanın içeriğini okur — **sandbox'lı** |
| `list_directory` | Bir dizinin içeriğini listeler — **sandbox'lı** |
| `write_file` | Bir dosyaya metin içerik yazar — **sandbox'lı**, var olan dosyaya yazmak için `overwrite=true` şart |
| `delete_file` | Bir dosyayı siler — **sandbox'lı**, geri alınamaz, `confirm=true` şart |
| `rename_file` | Bir dosyayı yeniden adlandırır/taşır — **sandbox'lı** (hem kaynak hem hedef), hedef zaten varsa `overwrite=true` şart |
| `list_windows` | Açık Hyprland pencerelerini listeler — **salt-okunur** (`hyprctl -j clients`) |
| `list_workspaces` | Hyprland workspace'lerini listeler — **salt-okunur** (`hyprctl -j workspaces`) |
| `active_window` | Odaklanmış pencerenin bilgisini döner — **salt-okunur** (`hyprctl -j activewindow`) |

### Dosya sistemi araçları — güvenlik modeli

Tüm dosya sistemi araçları (`filesystem.py`) bilinçli olarak dar bir
yetki yüzeyiyle tasarlandı:

- **Sadece dosyalar** — hiçbir araç dizin silmiyor/yeniden adlandırmıyor;
  bir dizin path'i verilirse hata döner. Kapsam bilinçli olarak dar
  tutuluyor.
- **Sandbox'lı kök dizin** — tüm yollar bir kök dizine (varsayılan:
  kullanıcının ev dizini, `NAVIGATOR_MCP_FS_ROOT` ortam değişkeniyle
  geçersiz kılınabilir) göre çözümlenir; `os.path.realpath` ile kanonik
  forma indirgenip kökün dışına çıkmadığı doğrulanır. `../` ile path
  traversal ve kök dışına mutlak yol verme denemeleri engellenir
  (gerçek MCP protokolü üzerinden test edildi — bkz. testler). Bu kontrol
  `write_file`, `delete_file` ve `rename_file` (hem kaynak hem hedef)
  için aynen geçerli.
- **Yazma için ek korumalar** — `write_file` var olan bir dosyanın üzerine
  ancak `overwrite=true` ile yazabilir (yanlışlıkla veri kaybını
  önlemek için); üst dizin zaten var olmalı (araç kendiliğinden dizin
  oluşturmaz, kapsamı dosya içeriğiyle sınırlı tutar); bir dizin path'ine
  yazma denemesi hata verir.
- **Silme için ek koruma** — `delete_file` geri alınamaz bir işlem
  olduğundan `confirm=true` olmadan hiçbir şey silmez; yanlışlıkla
  çağrılırsa (LLM'in kendi kendine tetiklemesi dahil) varsayılan olarak
  hata döner.
- **Yeniden adlandırma için ek koruma** — `rename_file`, `write_file` ile
  tutarlı: hedef zaten varsa `overwrite=true` gerekir, hedefin üst dizini
  zaten var olmalı.
- **Boyut sınırı** — `read_file` en fazla ~1 MB okur (`MAX_READ_BYTES`),
  `write_file` en fazla ~1 MB yazar (`MAX_WRITE_BYTES`), `list_directory`
  en fazla 500 girdi döner (`MAX_LIST_ENTRIES`) — büyük dosya/dizinlerin
  context'i boğmasını önlemek için.

### Hyprland araçları — kapsam ve sınırlama

`list_windows`, `list_workspaces` ve `active_window` (`hyprland.py`)
bilinçli olarak **salt-okunur** — workspace değiştirme, pencere
kapatma/taşıma gibi dispatch komutları YOK. `hyprctl -j <komut>`'u
subprocess ile çağırıp JSON çıktısını döndürür.

Geliştirme ortamı Debian/Pardus olduğundan (Hyprland bu dağıtımda
paketli değil) bu üç araç yerel makinede test edilemiyor — ama CI'da
GERÇEK bir Hyprland compositor'a karşı doğrulandı (aşağıya bkz.).
Bunlara ek olarak:

1. Mock'lanmış `subprocess.run`/`shutil.which` ile unit test edildi
   (`tests/test_hyprland.py`).
2. Gerçek bir stdio MCP oturumunda, Hyprland çalışmıyorken araçların
   çökmeden net bir hatayla (`isError: true`, `HyprlandError` mesajı)
   graceful başarısız olduğu doğrulandı (`tests/
   test_hyprland_integration.py`) — cloud-bridge'in kimlik bilgisiz
   yolunun doğrulanmasıyla aynı desen.

**Gerçek compositor'a karşı doğrulandı (CI, 2026-07-18):**
`.github/workflows/build-disk-and-boot-test.yml`'deki `hyprland-test`
job'ı, gerçek bir Navigator disk imajını QEMU'da (`virtio-gpu-pci` +
`-display vnc`, host'ta GPU/EGL gerektirmez — misafir kendi Mesa/
llvmpipe'ıyla yazılımda render ediyor) boot edip Hyprland'ı gerçekten
başlatıyor ve `mcp_tools.hyprland` fonksiyonlarını doğrudan çağırıyor.
Yolda iki gerçek sorun çıktı ve çözüldü:

- Hyprland kasıtlı olarak root'u reddediyor — CI'da yalnızca root SSH
  erişimi var, `--i-am-really-stupid` bayrağıyla aşıldı.
- aquamarine'ın DRM backend'i `libseat_open_seat()` ile bir seat açmaya
  çalışıyor; SSH oturumunun systemd-logind'de gerçek bir seat'i
  olmadığından bu başarısız oluyordu (`CBackend::create() failed!`).
  imajda `seatd` paketi yoktu (`rpm -q seatd` → "package seatd is not
  installed", `loginctl` → SEAT sütunu "-"); paket eklendi
  (`image/Containerfile`) ve test betiği Hyprland'dan önce seatd'yi
  arka planda başlatıp `LIBSEAT_BACKEND=seatd` ayarlıyor.

Sonuç — gerçek `hyprctl monitors` çıktısı (QEMU sanal monitörü):

```
Monitor Virtual-1 (ID 0):
	1280x800@74.99400 at 0x0
	description: Red Hat Inc. QEMU Monitor
	...
	focused: yes
```

Ve gerçek `mcp_tools.hyprland` çağrıları (mock değil):

```
list_windows: []
list_workspaces: [{"id": 1, "name": "1", "monitor": "Virtual-1", "monitorID": 0, "windows": 0, "hasfullscreen": false, "lastwindow": "0x0", "lastwindowtitle": "", "ispersistent": false}]
```

(`list_windows` boş dönüyor çünkü hiçbir pencere açılmadı — beklenen
davranış; `active_window` de aynı yolla doğrulanabilir ama test
betiğine henüz eklenmedi.)

## Kullanım

Harici bağımlılık yok, sadece Python 3.11+ (stdlib). `hardware-probe` ve
`router`'ın yanında (kardeş dizinler olarak) bulunması gerekiyor.

Sunucuyu stdio üzerinden başlatmak (varsayılan):

```sh
cd ai-stack/mcp-tools
python3 -m mcp_tools
```

HTTP+SSE üzerinden başlatmak (kimlik doğrulama zorunlu, bkz. aşağıdaki
bölüm):

```sh
cd ai-stack/mcp-tools
python3 -m mcp_tools --http --port 8765   # --host ile adres de değiştirilebilir
# token verilmezse otomatik üretilir ve stderr'e yazdırılır; sabit bir
# token için: --token <TOKEN> veya NAVIGATOR_MCP_HTTP_TOKEN ortam değişkeni
```

Dosya sistemi araçlarının kök dizinini değiştirmek için (varsayılan: ev
dizini):

```sh
NAVIGATOR_MCP_FS_ROOT=/istediğin/kök python3 -m mcp_tools
```

stdio'da: stdin'e newline-delimited JSON-RPC mesajları yazılır, yanıtlar
stdout'tan aynı şekilde okunur (bkz. `tests/test_integration.py`'daki
örnek oturum: `initialize` → `notifications/initialized` → `tools/list` →
`tools/call`).

Testler:

```sh
cd ai-stack/mcp-tools
python3 -m unittest discover -v -s tests
```

## Gerçek oturum örneği

Bu makinede gerçek bir stdio oturumu çalıştırıldı (izole bir sandbox
dizinine karşı, `NAVIGATOR_MCP_FS_ROOT` ile):

```
tools/list -> ["hardware_tier", "route_request", "read_file", "list_directory", "write_file", "delete_file", "rename_file", "list_windows", "list_workspaces", "active_window"]
tools/call(read_file, {"path": "hello.txt"}) -> {"content": [{"type": "text", "text": "merhaba navigator"}], "isError": false}
tools/call(list_directory, {}) -> {"content": [{"type": "text", "text": "[{\"name\": \"hello.txt\", ...}, {\"name\": \"subdir\", ...}]"}], "isError": false}
tools/call(read_file, {"path": "../../../../etc/passwd"}) -> {"content": [{"type": "text", "text": "Araç hatası: '...' izin verilen kök dizinin (...) dışına çıkıyor"}], "isError": true}
tools/call(write_file, {"path": "yeni.txt", "content": "navigator yazdı"}) -> {"content": [{"type": "text", "text": "16 bayt yazıldı: yeni.txt"}], "isError": false}
tools/call(write_file, {"path": "yeni.txt", "content": "tekrar"}) -> {"content": [{"type": "text", "text": "Araç hatası: Dosya zaten var: yeni.txt (üzerine yazmak için overwrite=true gerekir)"}], "isError": true}
tools/call(rename_file, {"path": "yeni.txt", "new_path": "yeniden-adli.txt"}) -> {"content": [{"type": "text", "text": "Yeniden adlandırıldı: yeni.txt -> yeniden-adli.txt"}], "isError": false}
tools/call(delete_file, {"path": "yeniden-adli.txt"}) -> {"content": [{"type": "text", "text": "Araç hatası: Silme geri alınamaz — onaylamak için confirm=true gerekir: yeniden-adli.txt"}], "isError": true}
tools/call(delete_file, {"path": "yeniden-adli.txt", "confirm": true}) -> {"content": [{"type": "text", "text": "Silindi: yeniden-adli.txt"}], "isError": false}
tools/call(list_windows, {}) -> {"content": [{"type": "text", "text": "Araç hatası: Hyprland çalışmıyor (HYPRLAND_INSTANCE_SIGNATURE ayarlı değil)"}], "isError": true}
```

(`list_windows` bu makinede beklendiği gibi hata veriyor — Hyprland
burada çalışmıyor. Gerçek bir compositor'da `isError: false` ve gerçek
pencere listesi dönmesi beklenir, Faz 3'te doğrulanacak.)

`mcp-tools → router → local-runtime → hardware-probe` zinciri de gerçek
MCP protokolü üzerinden uçtan uca çalışıyor (bkz. `route_request` aracı) —
hem stdio hem HTTP+SSE transport'unda aynı şekilde.

## HTTP+SSE transport

`http_transport.py`, MCP'nin 2024-11-05 spesifikasyonundaki klasik HTTP+SSE
modelini implemente eder (daha yeni "Streamable HTTP" değil — `server.py`
zaten `protocolVersion: "2024-11-05"` bildiriyor, tutarlı):

1. İstemci `GET /sse`'ye bağlanır — sunucu bir `session_id` üretir, ilk
   `endpoint` event'i ile istemcinin POST edeceği URI'yi
   (`/messages?session_id=<id>`) bildirir, sonra bağlantıyı açık tutar.
2. İstemci JSON-RPC isteklerini o URI'ye `POST` eder — sunucu isteği aynı
   `MCPServer.handle_message()` ile işler, **yanıtı HTTP body'sinde
   dönmez** (sadece `202 Accepted`), bunun yerine session'ın kuyruğuna
   ekler.
3. Kuyruğa eklenen yanıt, adım 1'de açılan SSE bağlantısı üzerinden
   `message` event'i olarak asenkron akar.

`ThreadingHTTPServer` kullanıldığından her bağlantı (uzun ömürlü SSE
GET'i dahil) kendi thread'inde çalışır — POST istekleri SSE bağlantısını
bloklamaz. Bilinmeyen/eksik `session_id` ile POST → `400`.

Bu makinede gerçek bir HTTP+SSE oturumu (gerçek TCP soketleri, subprocess)
uçtan uca çalıştırıldı: endpoint keşfi → `initialize`/`tools/list`/
`tools/call` POST'ları → SSE üzerinden doğru `id` eşleşmesiyle yanıtlar.

## Kimlik doğrulama (HTTP+SSE)

stdio transport zaten yerel bir süreç boru hattı olduğundan (işletim
sistemi süreç izolasyonu yeterli) kimlik doğrulaması gerektirmiyor. Ama
HTTP+SSE bir TCP soketi açtığı için (varsayılan `127.0.0.1` olsa bile)
`auth.py`'de implemente edilen Bearer token doğrulaması zorunlu:

- **Kimliksiz çalışma yok.** `--token` verilmezse veya
  `NAVIGATOR_MCP_HTTP_TOKEN` ortam değişkeni set değilse, sunucu
  `secrets.token_urlsafe(32)` ile otomatik bir token üretir ve
  başlangıçta stderr'e yazdırır — sessizce açık kapı olarak asla
  çalışmaz (Jupyter'ın notebook token modeliyle aynı ilke).
- **Her iki uç nokta da korunuyor** — `GET /sse` ve `POST /messages`,
  `Authorization: Bearer <token>` header'ı eksik veya yanlışsa `401`
  döner (`WWW-Authenticate: Bearer` header'ıyla birlikte).
- **Zamanlama saldırısına dayanıklı karşılaştırma** —
  `hmac.compare_digest` kullanılıyor, düz `==` değil.
- Token önceliği: `--token` CLI argümanı > `NAVIGATOR_MCP_HTTP_TOKEN` >
  otomatik üretim.

Gerçek TCP üzerinden doğrulandı: doğru token ile tam MCP oturumu (SSE +
POST), token'sız/yanlış token ile her iki uç noktada da `401` (bkz.
`tests/test_http_transport_integration.py`).

## Kapsam dışı — henüz yapılmadı

- Dizin silme/yeniden adlandırma/oluşturma yok — sadece dosyalar
  (`write_file` de yeni dizin oluşturmaz, üst dizin zaten var olmalı).
- Hyprland **kontrol** komutları yok — sadece sorgu (`list_windows`,
  `list_workspaces`, `active_window`). Workspace değiştirme, pencere
  odaklama/kapatma/taşıma gibi dispatch komutları bilinçli olarak
  eklenmedi (daha geniş bir yetki yüzeyi; CI'da gerçek Hyprland artık
  test edilebiliyor ama bu, kapsamı genişletme kararını henüz
  gerektirmedi).
- Quickshell ile konuşan araçlar yok.
- Hyprland araçları bu (Debian/Pardus) makinede test edilemiyor, ama
  CI'da gerçek bir compositor'a karşı doğrulandı — bkz. "Hyprland
  araçları — kapsam ve sınırlama". `active_window` henüz CI test
  betiğine eklenmedi (sadece `list_windows`/`list_workspaces`
  doğrulandı).
- TLS/HTTPS yok — Bearer token düz HTTP üzerinden taşınıyor; şu an sadece
  `127.0.0.1` varsayımıyla güvenli, dışa açık kullanım için TLS şart.
- MCP'nin daha yeni "Streamable HTTP" transport'u yok — sadece klasik
  HTTP+SSE (2024-11-05).

## Durum

Faz 2 — MCP sunucusu (`protocol.py`, `server.py`, `tools.py`), dosya
sistemi araçları (`filesystem.py` — okuma, listeleme, kontrollü yazma,
silme VE yeniden adlandırma), HTTP+SSE transport (`http_transport.py`),
Bearer token kimlik doğrulaması (`auth.py`) VE Hyprland sorgu araçları
(`hyprland.py` — salt-okunur, mock'lanmış + graceful-hata testleriyle
doğrulandı) tamamlandı, `python3 -m mcp_tools [--http] [--token T]`
CLI.
88 test geçiyor (protokol round-trip, server dispatch, gerçek modüllere
karşı araç testleri, path traversal engellemesi, overwrite koruması ve
confirm zorunluluğu dahil dosya sistemi testleri, session registry unit
testleri, auth yardımcı fonksiyon testleri, mock'lanmış Hyprland
testleri, ve gerçek subprocess/TCP soketleriyle iki transport üzerinden
uçtan uca MCP protokol testleri — kimlik doğrulamalı/doğrulamasız
istekler ve Hyprland'ın graceful hata yolu dahil).
