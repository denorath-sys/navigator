# ai-stack/hardware-probe/

## Ne yapacak

Sistem açılışında (veya talep üzerine) donanımı tarar ve Navigator'ın hangi
"model tier"ını çalıştırabileceğine karar verir: GPU var mı/yok mu, VRAM/RAM
miktarı, CPU çekirdek sayısı, NPU varlığı (varsa) gibi sinyalleri toplar.

Bu tier kararı, `local-runtime/`'ın hangi model boyutunu (ör. 3B / 8B / 14B
parametre sınıfı) yerel çalıştıracağını ve `router/`'ın ne zaman
`cloud-bridge/`'e yönlendirme yapacağını belirler.

## Kapsam dışı (Faz 1)

- Gerçek donanım tarama kodu yazılmayacak.
- Herhangi bir model indirme/test etme yapılmayacak.

## Beklenen çıktı formatı (taslak fikir)

Bir sonraki fazda, bu modülün üreteceği çıktı muhtemelen basit bir JSON
tier raporu olacak (ör. `{"tier": "mid", "vram_gb": 8, "has_gpu": true}`);
kesin şema Faz 2'de belirlenecek.

## Durum

Faz 1 — placeholder. Kod yok.
