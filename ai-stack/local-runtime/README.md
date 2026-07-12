# ai-stack/local-runtime/

## Ne yapıyor

`hardware-probe/`'un belirlediği tier'a uygun bir yerel LLM'i cihaz üzerinde
çalıştırır. **Mimari karar (Faz 2): [Ollama](https://ollama.com)** —
llama.cpp yerine tercih edildi çünkü temiz bir REST API (`localhost:11434`)
ve isme göre model çekme/yönetme sağlıyor; `router/`'ın tek bir HTTP
istemcisiyle konuşması yeterli, ayrı bir model dosyası/quantization yönetimi
gerekmiyor. Amaç, internet bağlantısı olmadan da temel asistan işlevlerinin
çalışabilmesi.

**Bu makinede artık tam çalışır durumda**: Ollama kurulu + `llama3.2:3b`
indirilmiş → `model_ready: true` → gerçek yerel üretim yapılabiliyor.

**`router` entegrasyonu (Faz 2):** `route: "local"` kararı verildiğinde
`router/local.py` bu modülü subprocess ile `--prompt` bayrağıyla çağırır —
bkz. `ai-stack/router/README.md` "local-runtime entegrasyonu".

## Kullanım

Harici bağımlılık yok, sadece Python 3.11+ (stdlib). `hardware-probe`'un
yanında (kardeş dizin olarak) bulunması gerekiyor.

```sh
cd ai-stack/local-runtime
python3 -m local_runtime --pretty                     # sadece durum
python3 -m local_runtime --prompt "merhaba" --pretty   # gerçek istek (önerilen modelle)
```

Testler:

```sh
cd ai-stack/local-runtime
python3 -m unittest discover -v -s tests
```

## Çıktı örneği

Bu makinede (Ollama kurulu ve çalışıyor, `llama3.2:3b` indirilmiş —
`hardware-probe` tier="low" tespit etti):

```json
{
  "schema_version": "0.1",
  "hardware_tier": "low",
  "recommended_model": {"model": "llama3.2:3b", "approx_size_gb": 2.0},
  "ollama_available": true,
  "installed_models": ["llama3.2:3b"],
  "model_ready": true
}
```

`--prompt` verildiğinde — **gerçek bir yerel üretim** (bu makinede test
edildi):

```json
{
  "schema_version": "0.1",
  "provider": "ollama",
  "hardware_tier": "low",
  "prompt_preview": "Merhaba, sen kimsin?",
  "model": "llama3.2:3b",
  "status": "ok",
  "content": "Merhaba! Ben bir model conversasyon otomatuım. Ne gibi yardımcı olabilirim?"
}
```

Model kurulu değilken/Ollama kapalıyken `status: "unavailable"` ve şu üç
`reason` değerinden biri döner: `no_local_model_recommended` (tier
"minimal"), `ollama_not_running` (Ollama kapalı), `model_not_installed`
(Ollama açık ama model çekilmemiş).

## Tier → model eşlemesi (taslak, `local_runtime/models.py`)

| Tier | Önerilen model | Yaklaşık boyut |
|---|---|---|
| `minimal` | *(yok — cloud-bridge'e yönlendirilmeli)* | — |
| `low` | `llama3.2:3b` | ~2 GB |
| `mid` | `llama3.1:8b` | ~4.7 GB |
| `high` | `llama3.1:70b` | ~40 GB |

Bu eşleme taslaktır, gerçek kullanım/benchmark verisi biriktikçe Faz 3+'ta
revize edilecek. Bu makinede sadece `low` tier'ın modeli (`llama3.2:3b`)
indirildi — `mid`/`high` bu donanıma hiç uygulanmıyor.

## İndirme tamamlandı (kullanıcı onayıyla, iki ayrı adımda)

1. **Ollama'nın kendisi**: `curl -fsSL https://ollama.com/install.sh | sh`
   (~1.37 GB, resmi kurulum betiği, sudo ile systemd servisi olarak). Bu
   makinede ayrık GPU olmadığından CPU-only modda kuruldu.
2. **Model ağırlığı**: `ollama pull llama3.2:3b` (~2 GB).

İkisi de ayrı, açık onaylarla yapıldı (proje kısıtı: 200 MB üstü indirme
onaysız başlatılmaz).

## Bilinen sınırlama — zaman aşımı

`OllamaClient.generate()`'ın varsayılan timeout'u 300 saniye —
`is_available()`/`list_models()` gibi hafif metadata çağrılarından çok daha
yüksek, çünkü model ilk çağrıda belleğe yüklenip CPU'da çıkarım yapması
dakikalar sürebilir (bu hata gerçek makinede yakalanıp düzeltildi: ilk
denemede varsayılan 5 saniyelik timeout'la `"error": "timed out"` alınmıştı).

## Durum

Faz 2 — orkestrasyon/istemci katmanı, `router` entegrasyonu, **gerçek
Ollama kurulumu VE gerçek model indirme** tamamlandı (`models.py`,
`client.py`, `status.py`, `python3 -m local_runtime [--prompt ...]` CLI).
16 test geçiyor — biri gerçek bir Ollama `generate()` çağrısı (model
belleğe yüklenip gerçek metin üretiyor). `route: "local"` artık bu
makinede gerçekten uçtan uca çalışıyor.
