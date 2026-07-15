# ai-stack/cloud-bridge/

## Ne yapıyor

`router/` yerel modelin yetersiz olduğuna veya kullanıcının bulut tercih
ettiğine karar verdiğinde devreye giren köprü. **Sağlayıcı: Anthropic Claude
API** (`claude-opus-4-8` varsayılan model). Kimlik bilgisi tespiti
(`ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN`) ve `/v1/messages` isteği
gönderen bir istemci sağlar.

`mcp-tools/` üzerinden gelen araç çağrılarının bulut modeller için de aynı
şekilde çalışmasını sağlamak (Faz 3+) bu modülün sorumluluğunda olacak.

**`router` entegrasyonu (Faz 2):** `route: "cloud"` kararı verildiğinde
`router/cloud.py` bu modülü subprocess ile `--prompt` bayrağıyla çağırır —
bkz. `ai-stack/router/README.md` "Cloud-bridge entegrasyonu".

## Neden resmi SDK değil

Anthropic'in resmi `anthropic` Python SDK'sı (kimlik bilgisi çözümlemesi,
OAuth profilleri, Workload Identity Federation dahil) genel amaçlı Claude
entegrasyonları için önerilen yoldur. Burada bilinçli olarak **stdlib-only
ham HTTP** tercih edildi çünkü:

- Diğer dört ai-stack modülü (`hardware-probe`, `local-runtime`, `router`,
  `mcp-tools`) aynı ilkeyle yazıldı — tutarlılık.
- Navigator OS nihayetinde `image/Containerfile` üzerinden rpm-ostree/dnf ile
  paketlenecek; pip bağımlılıkları bu modele uymuyor (ayrı bir RPM paketleme
  adımı gerektirir).
- Sadece kimlik bilgisi durumu raporlanıyor, gerçek bir API çağrısı henüz
  yapılmıyor — SDK'nın asıl değeri (tool use, streaming, retry mantığı)
  şu an kullanılmıyor.

**Bilinen sınırlama:** Sadece `ANTHROPIC_API_KEY` ve `ANTHROPIC_AUTH_TOKEN`
ortam değişkenleri destekleniyor — resmi SDK'nın yaptığı OAuth profili
(`ant auth login`) veya Workload Identity Federation çözümlemesi YOK.

## Kullanım

Harici bağımlılık yok, sadece Python 3.11+ (stdlib).

```sh
cd ai-stack/cloud-bridge
python3 -m cloud_bridge --pretty                     # sadece kimlik bilgisi durumu
python3 -m cloud_bridge --prompt "merhaba" --pretty   # gerçek istek (kimlik bilgisi varsa)
```

**`--converse`** (Faz 4'te `ai-stack/assistant` için eklendi): stdin'den
tam bir mesaj listesi + isteğe bağlı `tools` şeması okur, Claude API'nin
HAM yanıtını (`tool_use` blokları, `stop_reason` dahil — `--prompt`'un
basitleştirilmiş raporunun aksine) stdout'a basar. Çok turlu tool-use
döngüsü kuran çağıranlar için (`--prompt` tek turlu ve tool'suz kalmaya
devam ediyor):

```sh
echo '{"messages": [{"role": "user", "content": "merhaba"}], "tools": [...]}' \
  | python3 -m cloud_bridge --converse
```

Testler:

```sh
cd ai-stack/cloud-bridge
python3 -m unittest discover -v -s tests
```

### Kimlik bilgisini yerel olarak bağlamak (`.env.local`)

Bu makinede gerçek bir Anthropic API key `.env.local` dosyasına yazıldı
(`.gitignore`'da `.env*` deseni ile hariç tutuluyor — asla commit
edilmez, sadece bu geliştirme makinesinde var). Kullanmak için her
zaman elle source edilmesi gerekiyor (Bash tool çağrıları arasında
shell state kalıcı değil):

```sh
cd ai-stack/cloud-bridge
set -a && source .env.local && set +a
python3 -m cloud_bridge --prompt "merhaba" --pretty
```

Kimlik bilgisine bağlı testler (`test_prompt_cli.py`,
`router/tests/test_integration.py`) `.env.local` source edilmediğinde
otomatik `skip` olur (CI'da da böyle davranır — GitHub Actions'ta bu
secret yok) — sadece source edildiğinde gerçek bir API çağrısıyla
çalışır.

## Çıktı örneği

Kimlik bilgisi ayarlı değilken:

```json
{
  "schema_version": "0.1",
  "provider": "anthropic",
  "default_model": "claude-opus-4-8",
  "credentials_configured": false
}
```

`--prompt` verildiğinde (kimlik bilgisi yokken):

```json
{
  "schema_version": "0.1",
  "provider": "anthropic",
  "model": "claude-opus-4-8",
  "prompt_preview": "merhaba",
  "status": "unavailable",
  "reason": "credentials_not_configured"
}
```

`.env.local` source edilip kimlik bilgisi varken (bu makinede gerçek bir
API çağrısıyla doğrulandı):

```json
{
  "schema_version": "0.1",
  "provider": "anthropic",
  "model": "claude-opus-4-8",
  "prompt_preview": "Tek kelimeyle cevap ver: Türkiye'nin başkenti neresi?",
  "status": "ok",
  "content": "Ankara"
}
```

## `is_available()` neden ağ çağrısı yapmıyor

`local-runtime`'ın `OllamaClient.is_available()`'ı `localhost:11434/api/version`'a
gerçek bir çağrı yapar (ücretsiz, yerel). Anthropic API'sinde ücretsiz bir
"ping" uç noktası yok — bu yüzden `AnthropicClient.is_available()` sadece
ortam değişkeni varlığını kontrol ediyor, gerçek bir istek göndermiyor.

## Kapsam dışı — henüz yapılmadı

- Gizlilik filtrelemesi (isteğe gönderilmeden önce hassas veri maskeleme) yok.
- Streaming yok — her yanıt tek seferde, tam olarak döner.
- Kimlik bilgisi sadece bu geliştirme makinesinde (`.env.local`) —
  GitHub Actions'ta secret olarak tanımlı değil, dolayısıyla CI'da bulut
  yolu hâlâ "unavailable" (bu bilinçli bir sınır: `.env.local` hiçbir
  yerde commit edilmiyor).

## Durum

Faz 2 — kimlik bilgisi/istemci katmanı, `router` entegrasyonu VE gerçek
bir Claude API kimlik bilgisi bağlantısı tamamlandı (`client.py`,
`status.py`, `python3 -m cloud_bridge [--prompt ...]` CLI). Faz 4'te
çok turlu mesaj + tool-use desteği eklendi (`send_messages()`,
`--converse`) — `ai-stack/assistant`'ın gerçek bir tool-use döngüsü
kurabilmesi için. Gerçek bir API key `.env.local`'a yazıldı (gitignore'lı)
ve gerçek isteklerle uçtan uca doğrulandı — hem doğrudan `cloud_bridge`
CLI'ı hem `router → cloud_bridge` zinciri hem de `assistant`'ın gerçek
tool-use döngüsü üzerinden (mcp-tools'un `hardware_tier` aracını gerçekten
çağırıp doğru donanım verisiyle cevap üretti). 20 test geçiyor (mock'lanmış
HTTP + gerçek CLI entegrasyon testleri; kimlik bilgisiz yol her zaman
çalışır, kimlik bilgili gerçek-API testleri `.env.local` source
edilmediğinde otomatik `skip` olur).
