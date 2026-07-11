# ai-stack/mcp-tools/

## Ne yapıyor

Navigator asistanının sistemle etkileşim kurmasını sağlayan araç katmanı.
[Model Context Protocol (MCP)](https://modelcontextprotocol.io) standardını
kullanarak, hem yerel hem bulut modellerinin aynı araç setine tek bir
arayüzle erişmesini sağlar — `router/` hangi modeli seçtiğinden bağımsız
olarak araç çağrıları bu modül üzerinden yürütülür.

**Mimari karar (Faz 2):** MCP protokolü, resmi `mcp` Python SDK'sı
kurulmadan, stdlib-only newline-delimited JSON-RPC 2.0 stdio transport'u
doğrudan implemente edilerek yazıldı — diğer ai-stack modülleriyle aynı
"harici bağımlılık yok" ilkesi korundu.

## İlk araçlar

Şu an iki araç kayıtlı, ikisi de zaten çalışan diğer ai-stack modüllerini
subprocess üzerinden sarmalıyor:

| Araç | Sarmaladığı modül | Açıklama |
|---|---|---|
| `hardware_tier` | `hardware-probe` | Donanım tier'ını ve CPU/RAM/GPU sinyallerini döner |
| `route_request` | `router` | Bir isteğin yerel mi bulut mu ile karşılanacağına karar verir |

## Kullanım

Harici bağımlılık yok, sadece Python 3.11+ (stdlib). `hardware-probe` ve
`router`'ın yanında (kardeş dizinler olarak) bulunması gerekiyor.

Sunucuyu stdio üzerinden başlatmak:

```sh
cd ai-stack/mcp-tools
python3 -m mcp_tools
```

Sonra stdin'e newline-delimited JSON-RPC mesajları yazılır, yanıtlar
stdout'tan aynı şekilde okunur (bkz. `tests/test_integration.py`'daki
örnek oturum: `initialize` → `notifications/initialized` → `tools/list` →
`tools/call`).

Testler:

```sh
cd ai-stack/mcp-tools
python3 -m unittest discover -v -s tests
```

## Gerçek oturum örneği

Bu makinede gerçek bir stdio oturumu çalıştırıldı (bkz. commit geçmişi):

```
initialize -> {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "navigator-mcp-tools", "version": "0.1.0"}}
tools/list -> {"tools": [{"name": "hardware_tier", ...}, {"name": "route_request", ...}]}
tools/call(hardware_tier) -> {"content": [{"type": "text", "text": "{\"tier\": \"low\", ...}"}], "isError": false}
tools/call(route_request, {"prompt": "merhaba navigator", "prefer": "privacy"}) -> {"content": [...], "isError": false}
```

Yani şu an `mcp-tools → router → local-runtime → hardware-probe` zinciri
gerçek MCP protokolü üzerinden uçtan uca çalışıyor.

## Kapsam dışı — henüz yapılmadı

- Dosya sistemi / uygulama kontrolü gibi daha geniş sistem araçları yok —
  sadece zaten var olan iki modülü sarmalayan araçlar var.
- HTTP/SSE transport yok, sadece stdio.
- Kimlik doğrulama / yetkilendirme yok (Faz 1 sınırlamalarıyla aynı ilke:
  önce çalışan bir iskelet, güvenlik sertleştirmesi sonra).

## Durum

Faz 2 — ilk MCP sunucusu tamamlandı (`protocol.py`, `server.py`, `tools.py`,
`python3 -m mcp_tools` CLI). 16 test geçiyor (protokol round-trip, server
dispatch unit testleri, gerçek modüllere karşı araç testleri, ve gerçek
stdio subprocess'iyle uçtan uca MCP protokol testi).
