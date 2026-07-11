# ai-stack/hardware-probe/

## Ne yapıyor

Sistem açılışında (veya talep üzerine) donanımı tarar ve Navigator'ın hangi
"model tier"ını çalıştırabileceğine karar verir: CPU çekirdek sayısı/modeli,
toplam RAM, GPU varlığı/üreticisi/VRAM'ı (mümkünse), NPU varlığı (henüz
uygulanmadı) gibi sinyalleri toplayıp tek bir JSON raporunda birleştirir.

Bu tier kararı, `local-runtime/`'ın hangi model boyutunu (ör. 3B / 8B / 14B
parametre sınıfı) yerel çalıştıracağını ve `router/`'ın ne zaman
`cloud-bridge/`'e yönlendirme yapacağını belirleyecek (Faz 3+).

## Kullanım

Harici bağımlılık yok, sadece Python 3.11+ (stdlib).

```sh
cd ai-stack/hardware-probe
python3 -m hardware_probe --pretty
```

Testler:

```sh
cd ai-stack/hardware-probe
python3 -m unittest discover -v -s tests
```

## Çıktı şeması (v0.1)

```json
{
  "schema_version": "0.1",
  "cpu": {"model": "...", "cores_logical": 6, "cores_physical": 6},
  "memory": {"total_kb": 16195024, "total_gb": 15.4},
  "gpu": {
    "devices": [
      {"card": "card0", "vendor": "intel", "vendor_id": "0x8086",
       "driver": "i915", "vram_gb": null, "dedicated": false}
    ],
    "has_dedicated_gpu": false,
    "best_vram_gb": 0.0
  },
  "npu": {"present": false, "note": "NPU tespiti henüz uygulanmadı (Faz 3+)"},
  "tier": "low",
  "tier_reasoning": "RAM 15.4 GB >= 8 ama mid eşiği (16 GB + 6 GB VRAM) karşılanmadı"
}
```

Tier eşikleri (`hardware_probe/tier.py` içinde belgelenmiştir):

| Tier | Koşul |
|---|---|
| `minimal` | RAM < 8 GB, ayrık GPU yok |
| `low` | RAM >= 8 GB, mid eşiği karşılanmadı |
| `mid` | RAM >= 16 GB ve ayrık GPU VRAM >= 6 GB |
| `high` | RAM >= 32 GB ve ayrık GPU VRAM >= 12 GB |

Bu eşikler taslaktır; `local-runtime` gerçek benchmark verisi ürettikçe
Faz 3+'ta yeniden ayarlanacak.

## Bilinen sınırlamalar

- NVIDIA kartlarda VRAM miktarı sysfs üzerinden okunamıyor (proprietary
  sürücü `nvidia-smi` gerektirir) — `vram_gb: null` döner ama kart yine de
  `dedicated: true` sayılır.
- AMD entegre GPU'lar (APU) da `amdgpu` sürücüsünü kullandığından, ayrık bir
  Radeon kartla aynı şekilde `dedicated: true` işaretlenebilir. PCI
  device-id bazlı ayrım ileride eklenecek.
- NPU tespiti yok (Intel VPU / AMD XDNA / Qualcomm Hexagon için ortak bir
  sysfs arayüzü henüz yok).

## Durum

Faz 2 — ilk implementasyon tamamlandı. `cpu.py`, `memory.py`, `gpu.py`,
`npu.py`, `tier.py`, `probe.py` ve `python3 -m hardware_probe` CLI'ı mevcut;
20 unit/entegrasyon testi geçiyor, gerçek donanımda (Intel i5-8500, 15.4 GB
RAM, entegre Intel GPU) doğrulandı.
