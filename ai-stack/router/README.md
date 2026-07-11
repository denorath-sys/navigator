# ai-stack/router/

## Ne yapıyor

Navigator asistanına gelen her isteği, `local-runtime/`'ın raporladığı
donanım tier'ı + model hazırlığı, kullanıcı tercihi (gizlilik/maliyet/
hız/dengeli) ve isteğin kaba bir karmaşıklık tahminine göre `local` veya
`cloud` olarak etiketleyen karar katmanı. Karar `cloud` ise `cloud-bridge/`'i
**gerçekten çağırır** (bkz. "Cloud-bridge entegrasyonu" aşağıda). Asistan
panelinin (`shell/`) ve `mcp-tools/`'un birleştiği merkezi nokta olması
planlanıyor.

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

Bu makinede (Ollama kurulu değil → `model_ready: false` → her zaman `cloud`
→ `cloud-bridge` çağrılır ama kimlik bilgisi de yok):

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

## Cloud-bridge entegrasyonu

`route: "cloud"` kararı verildiğinde `router/cloud.py`, `python3 -m
cloud_bridge --prompt "<istek>"` komutunu subprocess ile çalıştırır ve
sonucu raporun `cloud_bridge` alanına ekler. Üç olası durum:

- Kimlik bilgisi yoksa: `{"status": "unavailable", "reason": "credentials_not_configured"}`
- Gerçek bir istek başarılı olursa: `{"status": "ok", "content": "..."}`
- Ağ/istek hatası olursa: `{"status": "error", "error": "..."}`

`route: "local"` kararında `cloud-bridge` hiç çağrılmaz (`local-runtime`'ın
gerçek `generate()` çağrısına bağlanması ayrı bir adım — henüz yapılmadı).

## Kapsam dışı — henüz yapılmadı

- `route: "local"` kararında `local-runtime`'ın gerçek `generate()` metodu
  çağrılmıyor — sadece `route: "cloud"` için `cloud-bridge` entegrasyonu var.
- `mcp-tools/` üzerinden gelen araç çağrıları `route_request` aracını
  kullanıyor (bkz. `ai-stack/mcp-tools`) ama bu da aynı sınırlamayı taşıyor.

## Durum

Faz 2 — karar/orkestrasyon katmanı ve **cloud-bridge entegrasyonu**
tamamlandı (`decision.py`, `status.py`, `cloud.py`, `python3 -m router`
CLI). 21 test geçiyor (saf karar mantığı unit testleri + gerçek 4 katmanlı
subprocess zinciri: router → local-runtime → hardware-probe VE router →
cloud-bridge, bu makinede uçtan uca doğrulandı — kimlik bilgisi olmadan
graceful `unavailable` durumu dahil).
