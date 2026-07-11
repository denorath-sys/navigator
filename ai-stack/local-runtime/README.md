# ai-stack/local-runtime/

## Ne yapıyor

`hardware-probe/`'un belirlediği tier'a uygun bir yerel LLM'i cihaz üzerinde
çalıştırır. **Mimari karar (Faz 2): [Ollama](https://ollama.com)** —
llama.cpp yerine tercih edildi çünkü temiz bir REST API (`localhost:11434`)
ve isme göre model çekme/yönetme sağlıyor; `router/`'ın tek bir HTTP
istemcisiyle konuşması yeterli, ayrı bir model dosyası/quantization yönetimi
gerekmiyor. Amaç, internet bağlantısı olmadan da temel asistan işlevlerinin
çalışabilmesi.

`router/` bu modülü, isteğin yerel olarak karşılanabileceğine karar
verdiğinde çağıracak (Faz 3+).

## Kullanım

Harici bağımlılık yok, sadece Python 3.11+ (stdlib). `hardware-probe`'un
yanında (kardeş dizin olarak) bulunması gerekiyor.

```sh
cd ai-stack/local-runtime
python3 -m local_runtime --pretty
```

Testler:

```sh
cd ai-stack/local-runtime
python3 -m unittest discover -v -s tests
```

## Çıktı örneği

Bu makinede (Ollama kurulu değil, hardware-probe tier="low" tespit etti):

```json
{
  "schema_version": "0.1",
  "hardware_tier": "low",
  "recommended_model": {"model": "llama3.2:3b", "approx_size_gb": 2.0},
  "ollama_available": false,
  "installed_models": [],
  "model_ready": false
}
```

## Tier → model eşlemesi (taslak, `local_runtime/models.py`)

| Tier | Önerilen model | Yaklaşık boyut |
|---|---|---|
| `minimal` | *(yok — cloud-bridge'e yönlendirilmeli)* | — |
| `low` | `llama3.2:3b` | ~2 GB |
| `mid` | `llama3.1:8b` | ~4.7 GB |
| `high` | `llama3.1:70b` | ~40 GB |

Bu eşleme taslaktır, gerçek kullanım/benchmark verisi biriktikçe Faz 3+'ta
revize edilecek.

## İndirme gerektiren kısım — henüz yapılmadı

Bu implementasyon **hiçbir model ağırlığı veya Ollama'nın kendisini
indirmedi/kurmadı** — proje kısıtı gereği (200 MB üstü indirme onaysız
başlatılmaz, model dosyaları birkaç GB). Şu an yazılan kod:

- Tier→model önerisi üretiyor (saf mantık, indirme yok)
- Ollama'nın REST API'sine konuşan bir istemci sağlıyor (Ollama kurulu
  değilken de mock'lanmış testlerle doğrulanabiliyor)
- Ollama kurulu değilken **çökmeden** `ollama_available: false` raporluyor
  (gerçek makinede doğrulandı — bu ortamda Ollama yok)

Ollama'nın kurulumu ve gerçek bir modelin (`ollama pull llama3.2:3b` ~2 GB)
indirilmesi ayrı, açık bir onay gerektiren adım olacak.

## Durum

Faz 2 — orkestrasyon/istemci katmanı tamamlandı (`models.py`, `client.py`,
`status.py`, `python3 -m local_runtime` CLI). 15 test geçiyor (mock'lanmış
Ollama HTTP + gerçek hardware-probe subprocess entegrasyonu). Ollama
kurulumu ve model indirme Faz 3+'ta, ayrı onayla yapılacak.
