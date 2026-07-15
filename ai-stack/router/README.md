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

**Bu makinede artık her iki yol da uçtan uca gerçek**: basit istekler
gerçekten yerel Ollama'da (`llama3.2:3b`) üretiliyor; karmaşık istekler
(tier="low" düşük kapasiteli sayıldığından) `cloud-bridge`'e düşüyor.

## Kullanım

Harici bağımlılık yok, sadece Python 3.11+ (stdlib). `local-runtime` ve
`cloud-bridge`'in yanında (kardeş dizinler olarak) bulunması gerekiyor.

```sh
cd ai-stack/router
python3 -m router --prompt "Merhaba, sen kimsin?" --pretty
python3 -m router --prompt "..." --prefer privacy   # balanced|privacy|cost|speed
python3 -m router --prompt "..." --decide-only      # sadece karar, ÇALIŞTIRMAZ (bkz. aşağıda)
```

**`--decide-only`** (Faz 4'te `ai-stack/assistant` için eklendi): sadece
route kararını (`complexity`/`hardware_tier`/`model_ready`/`route`/
`reasoning`) döner, `local-runtime` veya `cloud-bridge`'i ÇALIŞTIRMAZ.
`assistant` gibi kendi üretim akışını (örn. tool-use döngüsü) kurmak
isteyen çağıranlar için — router'ın kendi tool'suz `generate()` çağrısını
yapıp sonucu atmak hem israf hem gereksiz bir gerçek API çağrısı olurdu.

Testler:

```sh
cd ai-stack/router
python3 -m unittest discover -v -s tests
```

## Çıktı örneği — yerel yol (gerçek üretim)

Basit bir istek, bu makinede gerçekten çalıştırıldı:

```json
{
  "schema_version": "0.1",
  "prompt_preview": "Merhaba, sen kimsin?",
  "complexity": "simple",
  "preference": "balanced",
  "hardware_tier": "low",
  "model_ready": true,
  "route": "local",
  "reasoning": "model hazır ve istek yerel için uygun",
  "local_runtime": {
    "schema_version": "0.1",
    "provider": "ollama",
    "hardware_tier": "low",
    "prompt_preview": "Merhaba, sen kimsin?",
    "model": "llama3.2:3b",
    "status": "ok",
    "content": "Merhaba! Ben bir model conversasyon otomatuım. Ne gibi yardımcı olabilirim?"
  }
}
```

## Çıktı örneği — bulut yolu

Karmaşık (uzun) bir istek — tier="low" düşük kapasiteli sayıldığından
`model_ready: true` olsa bile `cloud`'a düşüyor. Claude API kimlik bilgisi
`cloud-bridge/.env.local` ile source edildiğinde (bkz. `ai-stack/
cloud-bridge/README.md`) gerçek bir yanıt döner, source edilmediğinde
(varsayılan, CI dahil) graceful "unavailable":

```json
{
  "schema_version": "0.1",
  "complexity": "complex",
  "hardware_tier": "low",
  "model_ready": true,
  "route": "cloud",
  "cloud_bridge": {
    "status": "ok",
    "model": "claude-opus-4-8",
    "content": "Ankara"
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

## local-runtime entegrasyonu

`route: "local"` kararı verildiğinde `router/local.py`, `python3 -m
local_runtime --prompt "<istek>"` komutunu subprocess ile çalıştırır ve
sonucu raporun `local_runtime` alanına ekler. Olası durumlar:

- `{"status": "ok", "content": "..."}` — gerçek istek başarılı (bu makinede
  doğrulandı)
- `{"status": "unavailable", "reason": "ollama_not_running"}` — Ollama kapalı
- `{"status": "unavailable", "reason": "model_not_installed"}` — Ollama açık
  ama önerilen model çekilmemiş
- `{"status": "unavailable", "reason": "no_local_model_recommended"}` — tier
  "minimal", yerel model önerilmiyor
- `{"status": "error", "error": "..."}` — ağ/istek hatası (ör. timeout)

**Bilinen sınırlama:** `OllamaClient.generate()`'ın varsayılan timeout'u
300 saniye — ilk denemede 5 saniyelik varsayılan timeout'la gerçek bir
üretim çağrısı zaman aşımına uğramıştı (model belleğe yükleniyor + CPU'da
çıkarım yapıyor), bu gerçek makinede yakalanıp düzeltildi.

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
- Bulut kimlik bilgisi sadece bu geliştirme makinesinde (`cloud-bridge/
  .env.local`, gitignore'lı) — CI'da secret olarak tanımlı değil, GitHub
  Actions'ta bulut yolu hâlâ "unavailable" raporlar.

## Durum

Faz 2 — karar/orkestrasyon katmanı, **local-runtime entegrasyonu** ve
**cloud-bridge entegrasyonu** tamamlandı (`decision.py`, `status.py`,
`local.py`, `cloud.py`, `python3 -m router` CLI). Faz 4'te `--decide-only`
bayrağı eklendi (bkz. yukarıda) — `ai-stack/assistant`'ın kendi üretim
akışını kurabilmesi için. 30 test geçiyor — biri gerçek bir yerel Ollama
üretimi (`route: "local"` uçtan uca, gerçek metin üretiyor), biri kimlik
bilgisiz bulut yönlendirmesi (`route: "cloud"`, graceful "unavailable" —
her zaman çalışır, CI dahil), biri de kimlik bilgili gerçek bulut üretimi
(`.env.local` source edildiğinde gerçek bir Claude API yanıtı — kimlik
bilgisi yoksa otomatik `skip`), üçü `--decide-only`'yi doğrular.
**`router` artık bu makinede tamamen gerçek çalışan bir sistem** —
hiçbir yol mock/placeholder değil, hem yerel hem bulut ucu gerçekten
üretim yapıyor.
