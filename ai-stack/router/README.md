# ai-stack/router/

## Ne yapıyor

Navigator asistanına gelen her isteği, `local-runtime/`'ın raporladığı
donanım tier'ı + model hazırlığı, kullanıcı tercihi (gizlilik/maliyet/
hız/dengeli) ve isteğin kaba bir karmaşıklık tahminine göre `local` veya
`cloud` olarak etiketleyen karar katmanı. Karar `local` ise `local-runtime/`'ı,
`cloud` ise `cloud-bridge/`'i **gerçekten çağırır** (bkz. entegrasyon
bölümleri aşağıda). Asistan panelinin (`shell/`) ve `mcp-tools/`'un
birleştiği merkezi nokta olması planlanıyor.

`router`, `hardware-probe`'u ayrıca çağırmaz — `local-runtime`'ın raporu
zaten `hardware_tier` ve `model_ready` alanlarını içeriyor, tek bir
subprocess hop'u yeterli (bkz. `router/status.py`).

## Kullanım

Harici bağımlılık yok, sadece Python 3.11+ (stdlib). `local-runtime` ve
`cloud-bridge`'in yanında (kardeş dizinler olarak) bulunması gerekiyor.

```sh
cd ai-stack/router
python3 -m router --prompt "Navigator'da workspace nasıl değiştiririm?" --pretty
python3 -m router --prompt "..." --prefer privacy   # balanced|privacy|cost|speed
```

Testler:

```sh
cd ai-stack/router
python3 -m unittest discover -v -s tests
```

## Çıktı örneği

Bu makinede (Ollama kurulu ve çalışıyor ama önerilen model henüz
indirilmedi → `model_ready: false` → her zaman `cloud` → `cloud-bridge`
çağrılır ama kimlik bilgisi de yok):

```json
{
  "schema_version": "0.1",
  "prompt_preview": "Navigator'da workspace nasıl değiştiririm?",
  "complexity": "simple",
  "preference": "balanced",
  "hardware_tier": "low",
  "model_ready": false,
  "route": "cloud",
  "reasoning": "yerel model hazır değil (Ollama kapalı veya model indirilmemiş)",
  "cloud_bridge": {
    "schema_version": "0.1",
    "provider": "anthropic",
    "model": "claude-opus-4-8",
    "prompt_preview": "Navigator'da workspace nasıl değiştiririm?",
    "status": "unavailable",
    "reason": "credentials_not_configured"
  }
}
```

`model_ready: true` olsaydı (`route: "local"`), rapora `cloud_bridge` yerine
`local_runtime` alanı eklenirdi — bkz. "local-runtime entegrasyonu" aşağıda.

## Karar mantığı (taslak, `router/decision.py`)

1. `model_ready == false` ise (Ollama kapalı veya model indirilmemiş):
   tercih ne olursa olsun **her zaman `cloud`**.
2. `privacy` veya `cost` tercihi: model hazırsa **her zaman `local`**.
3. `speed` tercihi: karmaşık istek + düşük tier (`minimal`/`low`) → `cloud`;
   aksi halde `local` (ağ gecikmesi yok).
4. `balanced` (varsayılan): karmaşık istek + düşük tier → `cloud`; aksi
   halde `local`.

Karmaşıklık tahmini (`estimate_complexity`) şimdilik çok kaba bir sezgisel
(kelime sayısı > 40 veya çok satırlı → "complex"); gerçek bir sınıflandırma
Faz 3+'ta ele alınacak. Tüm eşikler taslaktır.

## local-runtime entegrasyonu

`route: "local"` kararı verildiğinde `router/local.py`, `python3 -m
local_runtime --prompt "<istek>"` komutunu subprocess ile çalıştırır ve
sonucu raporun `local_runtime` alanına ekler. Olası durumlar:

- `{"status": "unavailable", "reason": "ollama_not_running"}` — Ollama kapalı
- `{"status": "unavailable", "reason": "model_not_installed"}` — Ollama açık
  ama önerilen model çekilmemiş
- `{"status": "unavailable", "reason": "no_local_model_recommended"}` — tier
  "minimal", yerel model önerilmiyor
- `{"status": "ok", "content": "..."}` — gerçek istek başarılı
- `{"status": "error", "error": "..."}` — ağ/istek hatası

Bu makinede Ollama kurulu ve çalışıyor ama önerilen model henüz
indirilmediğinden gerçek karar hep `cloud`'a düşüyor (`model_ready` her
zaman `false`, `reason: "model_not_installed"`); `local` yolu, karar
adımına sahte bir durum (`model_ready: true`) enjekte edilerek test edildi
— gerçek `local-runtime` subprocess'i yine de gerçek Ollama durumunu doğru
raporladı (bkz. `tests/test_integration.py`).

## Cloud-bridge entegrasyonu

`route: "cloud"` kararı verildiğinde `router/cloud.py`, `python3 -m
cloud_bridge --prompt "<istek>"` komutunu subprocess ile çalıştırır ve
sonucu raporun `cloud_bridge` alanına ekler. Üç olası durum:

- Kimlik bilgisi yoksa: `{"status": "unavailable", "reason": "credentials_not_configured"}`
- Gerçek bir istek başarılı olursa: `{"status": "ok", "content": "..."}`
- Ağ/istek hatası olursa: `{"status": "error", "error": "..."}`

Her karar sadece kendi hedefini çağırır: `local` iken `cloud-bridge`
çağrılmaz, `cloud` iken `local-runtime` çağrılmaz (testlerle doğrulandı).

## Kapsam dışı — henüz yapılmadı

- `mcp-tools/` üzerinden gelen araç çağrıları `route_request` aracını
  kullanıyor (bkz. `ai-stack/mcp-tools`) — bu artık hem `local` hem `cloud`
  entegrasyonunu otomatik olarak miras alıyor.
- Gerçek bir Ollama/Claude API yanıtı bu ortamda hiç görülmedi — Ollama
  kurulu olsa da model henüz indirilmediğinden ve Claude API kimlik bilgisi
  olmadığından, sadece "kullanılamıyor" yollarının doğru çalıştığı
  doğrulandı.

## Durum

Faz 2 — karar/orkestrasyon katmanı, **local-runtime entegrasyonu** ve
**cloud-bridge entegrasyonu** tamamlandı (`decision.py`, `status.py`,
`local.py`, `cloud.py`, `python3 -m router` CLI). 26 test geçiyor (saf karar
mantığı unit testleri + iki gerçek subprocess zinciri: router →
local-runtime → hardware-probe VE router → cloud-bridge, bu makinede uçtan
uca doğrulandı — model/kimlik bilgisi olmadan graceful `unavailable`
durumları dahil).
