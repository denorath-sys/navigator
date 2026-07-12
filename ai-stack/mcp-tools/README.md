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

Dört araç kayıtlı — ikisi zaten çalışan diğer ai-stack modüllerini
sarmalıyor, ikisi (Faz 2'nin ikinci adımı) gerçek, salt-okunur dosya
sistemi erişimi sağlıyor:

| Araç | Açıklama |
|---|---|
| `hardware_tier` | `hardware-probe`'u sarmalar — donanım tier'ını ve CPU/RAM/GPU sinyallerini döner |
| `route_request` | `router`'ı sarmalar — bir isteğin yerel mi bulut mu ile karşılanacağına karar verir (artık gerçek yerel üretim/bulut çağrısını da tetikliyor) |
| `read_file` | Bir dosyanın içeriğini okur — **salt-okunur, sandbox'lı** |
| `list_directory` | Bir dizinin içeriğini listeler — **salt-okunur, sandbox'lı** |

### Dosya sistemi araçları — güvenlik modeli

`read_file` ve `list_directory` (`filesystem.py`) bilinçli olarak en düşük
riskli ilk adım olarak tasarlandı:

- **Sadece okuma** — yazma, silme, yeniden adlandırma YOK.
- **Sandbox'lı kök dizin** — tüm yollar bir kök dizine (varsayılan:
  kullanıcının ev dizini, `NAVIGATOR_MCP_FS_ROOT` ortam değişkeniyle
  geçersiz kılınabilir) göre çözümlenir; `os.path.realpath` ile kanonik
  forma indirgenip kökün dışına çıkmadığı doğrulanır. `../` ile path
  traversal ve kök dışına mutlak yol verme denemeleri engellenir
  (gerçek MCP protokolü üzerinden test edildi — bkz. testler).
- **Boyut sınırı** — `read_file` en fazla ~1 MB okur (`MAX_READ_BYTES`),
  `list_directory` en fazla 500 girdi döner (`MAX_LIST_ENTRIES`) — büyük
  dosya/dizinlerin context'i boğmasını önlemek için.

## Kullanım

Harici bağımlılık yok, sadece Python 3.11+ (stdlib). `hardware-probe` ve
`router`'ın yanında (kardeş dizinler olarak) bulunması gerekiyor.

Sunucuyu stdio üzerinden başlatmak (varsayılan):

```sh
cd ai-stack/mcp-tools
python3 -m mcp_tools
```

HTTP+SSE üzerinden başlatmak:

```sh
cd ai-stack/mcp-tools
python3 -m mcp_tools --http --port 8765   # --host ile adres de değiştirilebilir
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
tools/list -> ["hardware_tier", "route_request", "read_file", "list_directory"]
tools/call(read_file, {"path": "hello.txt"}) -> {"content": [{"type": "text", "text": "merhaba navigator"}], "isError": false}
tools/call(list_directory, {}) -> {"content": [{"type": "text", "text": "[{\"name\": \"hello.txt\", ...}, {\"name\": \"subdir\", ...}]"}], "isError": false}
tools/call(read_file, {"path": "../../../../etc/passwd"}) -> {"content": [{"type": "text", "text": "Araç hatası: '...' izin verilen kök dizinin (...) dışına çıkıyor"}], "isError": true}
```

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

## Kapsam dışı — henüz yapılmadı

- Dosya **yazma**/silme/yeniden adlandırma yok — sadece okuma.
- Uygulama kontrolü (Hyprland/Quickshell ile konuşan araçlar) yok — bu
  makinede Hyprland çalışmadığından zaten gerçek test edilemez.
- Kimlik doğrulama / yetkilendirme yok — HTTP+SSE transport şu an
  kimliksiz/şifresiz (`127.0.0.1` varsayılan; dışa açık kullanım için
  güvenlik sertleştirmesi gerekir, bu Faz 1 sınırlamalarıyla aynı ilke:
  önce çalışan bir iskelet, güvenlik sertleştirmesi sonra).
- MCP'nin daha yeni "Streamable HTTP" transport'u yok — sadece klasik
  HTTP+SSE (2024-11-05).

## Durum

Faz 2 — MCP sunucusu (`protocol.py`, `server.py`, `tools.py`), dosya
sistemi araçları (`filesystem.py`) VE HTTP+SSE transport
(`http_transport.py`) tamamlandı, `python3 -m mcp_tools [--http]` CLI.
41 test geçiyor (protokol round-trip, server dispatch, gerçek modüllere
karşı araç testleri, path traversal engellemesi dahil dosya sistemi
testleri, session registry unit testleri, ve gerçek subprocess/TCP
soketleriyle iki transport üzerinden uçtan uca MCP protokol testleri).
