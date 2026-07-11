# ai-stack/cloud-bridge/

## Ne yapıyor

`router/` yerel modelin yetersiz olduğuna veya kullanıcının bulut tercih
ettiğine karar verdiğinde devreye giren köprü. **Sağlayıcı: Anthropic Claude
API** (`claude-opus-4-8` varsayılan model). Kimlik bilgisi tespiti
(`ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN`) ve `/v1/messages` isteği
gönderen bir istemci sağlar.

`mcp-tools/` üzerinden gelen araç çağrılarının bulut modeller için de aynı
şekilde çalışmasını sağlamak (Faz 3+) bu modülün sorumluluğunda olacak.

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
python3 -m cloud_bridge --pretty
```

Testler:

```sh
cd ai-stack/cloud-bridge
python3 -m unittest discover -v -s tests
```

## Çıktı örneği

Bu makinede (kimlik bilgisi ayarlı değil):

```json
{
  "schema_version": "0.1",
  "provider": "anthropic",
  "default_model": "claude-opus-4-8",
  "credentials_configured": false
}
```

## `is_available()` neden ağ çağrısı yapmıyor

`local-runtime`'ın `OllamaClient.is_available()`'ı `localhost:11434/api/version`'a
gerçek bir çağrı yapar (ücretsiz, yerel). Anthropic API'sinde ücretsiz bir
"ping" uç noktası yok — bu yüzden `AnthropicClient.is_available()` sadece
ortam değişkeni varlığını kontrol ediyor, gerçek bir istek göndermiyor.

## Kapsam dışı — henüz yapılmadı

- **Hiçbir gerçek API çağrısı yapılmadı/test edilmedi** — bu ortamda kimlik
  bilgisi yok, gerçek bir Claude API çağrısı maliyetli olacağından onaysız
  denenmedi. `generate()` metodu yazıldı ve mock'lanmış testlerle
  doğrulandı, ama canlı bir isteğe karşı hiç çalıştırılmadı.
- Gizlilik filtrelemesi (isteğe gönderilmeden önce hassas veri maskeleme) yok.
- `router`/`mcp-tools` entegrasyonu yok — `route: "cloud"` kararı bu modülü
  henüz gerçekten çağırmıyor.
- Tool use / streaming yok — sadece tek turluk `generate()`.

## Durum

Faz 2 — kimlik bilgisi/istemci katmanı tamamlandı (`client.py`, `status.py`,
`python3 -m cloud_bridge` CLI). 14 test geçiyor (mock'lanmış HTTP + gerçek
CLI entegrasyon testi, kimlik bilgisi olmadan). Bununla `ai-stack`'in beş
modülünün tamamı en az bir implementasyon aşamasına ulaştı.
