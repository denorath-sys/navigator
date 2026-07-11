# Navigator OS — Mimari Özet

Bu doküman, Faz 1 başlangıç yönergesinde tanımlanan nihai mimarinin özetidir.
Aşağıdaki bileşenlerin çoğu **ileride kurulacak**; bu doküman şu anki niyeti
kayıt altına almak içindir, mevcut implementasyon durumu için ilgili
klasörlerin README'lerine bakın.

## Katmanlar

### Taban işletim sistemi

**Fedora Atomic**, OSTree tabanlı, aylık güncellenen immutable bir imaj
olarak kurulacak. Kullanıcı sistemi doğrudan değiştirmez; değişiklikler
katmanlı imaj güncellemeleri (`rpm-ostree` / `bootc`) üzerinden gelir.
Referans base image: [`ublue-os/main`](https://github.com/ublue-os/main)
(Universal Blue). Tanım dosyası: [`image/Containerfile`](../image/Containerfile).

### Masaüstü ortamı

**Hyprland**, dinamik tiling özellikli bir Wayland compositor'ü olarak
seçildi — performans ve özelleştirilebilirlik önceliği. Üzerine
**Quickshell** veya **AGS** tabanlı özgün bir shell inşa edilecek (panel,
bildirimler, asistan paneli, launcher). Bkz. [`hyprland/`](../hyprland/) ve
[`shell/`](../shell/).

### AI Stack

Beş bileşenden oluşan hibrit yerel/bulut mimari:

1. **hardware-probe** — donanım tespiti, model tier kararı
2. **local-runtime** — llama.cpp/Ollama ile yerel model çalıştırma
3. **mcp-tools** — MCP (Model Context Protocol) tabanlı araç erişimi
4. **router** — istekleri yerel/bulut arasında yönlendiren karar katmanı
5. **cloud-bridge** — bulut model sağlayıcılarına bağlantı

Detaylar: [`ai-stack/README.md`](../ai-stack/README.md).

### Marka kimliği

Pusula, deniz feneri, Orion takımyıldızı ve Kuzey Yıldızı temalı
nautical/gökyüzü kimliği. Renk paleti: teal `#4fd1c5`, mor `#8b7cf6`,
altın `#e8d9a8`, lacivert taban `#0b0f1a`. Bkz.
[`theme/palette.json`](../theme/palette.json).

## Tasarım ilkeleri

- **AI, eklenti değil çekirdek:** Asistan paneli, masaüstünün ayrılmaz bir
  parçası olarak tasarlanır (üçüncü parti bir uygulama gibi değil).
- **Donanıma duyarlı:** Sistem, kullanıcının donanımına göre otomatik olarak
  uygun model tier'ını seçer; kullanıcıdan manuel yapılandırma beklenmez.
- **Gizlilik/maliyet tercihine saygı:** Router, kullanıcının yerel/bulut
  tercihini önceliklendirir; bulut her zaman varsayılan değildir.
- **Immutable & geri alınabilir:** OSTree tabanlı imaj modeli sayesinde
  sistem güncellemeleri atomik ve geri alınabilir.

## Faz durumu

Güncel yol haritası için kök [`README.md`](../README.md#yol-haritası)
dosyasına bakın.
