# ai-stack/local-runtime/

## Ne yapıyor

`hardware-probe/`'un belirlediği tier'a uygun bir yerel LLM'i cihaz üzerinde
çalıştırır. **Mimari karar (Faz 2): [Ollama](https://ollama.com)** —
llama.cpp yerine tercih edildi çünkü temiz bir REST API (`localhost:11434`)
ve isme göre model çekme/yönetme sağlıyor; `router/`'ın tek bir HTTP
istemcisiyle konuşması yeterli, ayrı bir model dosyası/quantization yönetimi
gerekmiyor. Amaç, internet bağlantısı olmadan da temel asistan işlevlerinin
çalışabilmesi.

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

Bu makinede (Ollama **kurulu ve çalışıyor** — `curl -fsSL https://ollama.com/install.sh | sh`
ile kuruldu, systemd servisi `active`; hardware-probe tier="low" tespit
etti; önerilen model henüz indirilmedi):

```json
{
  "schema_version": "0.1",
  "hardware_tier": "low",
  "recommended_model": {"model": "llama3.2:3b", "approx_size_gb": 2.0},
  "ollama_available": true,
  "installed_models": [],
  "model_ready": false
}
```

`--prompt` verildiğinde (aynı durum — Ollama açık, model kurulu değil):

```json
{
  "schema_version": "0.1",
  "provider": "ollama",
  "hardware_tier": "low",
  "prompt_preview": "merhaba",
  "status": "unavailable",
  "reason": "model_not_installed",
  "model": "llama3.2:3b"
}
```

`reason` üç değerden biri olabilir: `no_local_model_recommended` (tier
"minimal"), `ollama_not_running` (Ollama kapalı), `model_not_installed`
(Ollama açık ama önerilen model çekilmemiş — şu anki durum).

## Tier → model eşlemesi (taslak, `local_runtime/models.py`)

| Tier | Önerilen model | Yaklaşık boyut |
|---|---|---|
| `minimal` | *(yok — cloud-bridge'e yönlendirilmeli)* | — |
| `low` | `llama3.2:3b` | ~2 GB |
| `mid` | `llama3.1:8b` | ~4.7 GB |
| `high` | `llama3.1:70b` | ~40 GB |

Bu eşleme taslaktır, gerçek kullanım/benchmark verisi biriktikçe Faz 3+'ta
revize edilecek.

## İndirme gerektiren kısım — kısmen yapıldı

**Ollama'nın kendisi kuruldu** (kullanıcı onayıyla, `curl -fsSL
https://ollama.com/install.sh | sh` — ~1.37 GB, resmi kurulum betiği,
sudo ile systemd servisi olarak). Bu makinede ayrık GPU olmadığından
CPU-only modda kuruldu.

**Model ağırlığı henüz indirilmedi** — proje kısıtı gereği (birkaç GB'lık
model dosyaları için ayrı, açık bir onay gerekiyor). Şu an:

- Tier→model önerisi üretiyor (saf mantık)
- Ollama'nın REST API'sine gerçekten konuşuyor (`ollama_available: true`,
  gerçek makinede doğrulandı)
- Model kurulu olmadığından **çökmeden** `model_ready: false` /
  `reason: "model_not_installed"` raporluyor

`ollama pull llama3.2:3b` (~2 GB) ayrı, açık bir onay gerektiren bir
sonraki adım olacak.

## Durum

Faz 2 — orkestrasyon/istemci katmanı, `router` entegrasyonu VE **gerçek
Ollama kurulumu** tamamlandı (`models.py`, `client.py`, `status.py`,
`python3 -m local_runtime [--prompt ...]` CLI). 16 test geçiyor (mock'lanmış
Ollama HTTP + gerçek Ollama'ya karşı entegrasyon testleri — hem durum hem
`--prompt` yolu, `ollama_available: true` durumuyla). Model indirme Faz 3+'ta,
ayrı onayla yapılacak.
