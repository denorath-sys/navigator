# Navigator OS

Navigator, yapay zekayı üçüncü parti bir uygulama olarak değil, işletim
sisteminin doğal bir parçası olarak sunan bir Linux dağıtımı. Hedef kitle:
orta-üst düzey donanıma sahip geliştirici, oyuncu ve multimedya kullanıcıları.

Marka kimliği pusula, deniz feneri, Orion takımyıldızı ve Kuzey Yıldızı
temalı nautical/gökyüzü estetiğine dayanır (bkz. [`theme/palette.json`](theme/palette.json)).

## Mimari özet

| Katman | Seçim |
|---|---|
| Taban | Fedora Atomic (OSTree, aylık immutable imaj, [`image/Containerfile`](image/Containerfile)) |
| Compositor | [Hyprland](https://hyprland.org) (Wayland) — [`hyprland/`](hyprland/) |
| Shell | Quickshell veya AGS tabanlı özgün kabuk — [`shell/`](shell/) |
| AI Stack | Donanıma göre otomatik model tier seçimi, MCP tabanlı araç erişimi, yerel↔bulut hibrit router — [`ai-stack/`](ai-stack/) |
| Tema | Marka renk paleti + GTK/Qt tema — [`theme/`](theme/) |

Detaylı mimari doküman: [`docs/architecture.md`](docs/architecture.md).

## Yol haritası

- **Faz 1 — İskelet (şu an):** Repo yapısı, config/doküman taslakları,
  CI pipeline tanımı. Hiçbir büyük indirme veya gerçek build yapılmadı.
- **Faz 2 — Yerel prototip:** `ai-stack/hardware-probe` ve
  `ai-stack/local-runtime` ilk implementasyonu; shell teknolojisi (Quickshell
  vs AGS) kararı; gerçek Hyprland oturumunda config testi.
- **Faz 3 — İmaj build & test:** GitHub Actions üzerinde ilk gerçek
  `bootc`/`rpm-ostree` imaj build'i; sanal makinede boot testi.
- **Faz 4 — AI stack tamamlama:** `router`, `mcp-tools`, `cloud-bridge`
  implementasyonu; uçtan uca asistan paneli deneyimi.
- **Faz 5 — Kullanıcı testi & yayın hazırlığı:** Gerçek donanımda kurulum
  testleri, dokümantasyon, ilk topluluk sürümü.

## Proje kısıtları (geçerli olduğu sürece)

Bu proje şu an roaming/kısıtlı internet ile geliştiriliyor:

- 200 MB'ı aşan indirmeler (paket, ISO, model dosyası, container imajı)
  onay almadan yapılmaz.
- Ağır işlemler (`rpm-ostree compose`, gerçek ISO build, model indirme)
  yerel ortamda çalıştırılmaz; bunun yerine gereken script/config/CI
  pipeline dosyaları yazılır.
- Gerçek build/test işlemleri GitHub Actions üzerinde çalışır
  ([`.github/workflows/build-image.yml`](.github/workflows/build-image.yml)),
  proje sahibi tarafından tetiklenir.

## Katkı rehberi (taslak)

> Bu bölüm Faz 1 taslağıdır; proje topluluğa açıldığında genişletilecektir.

1. Issue açmadan önce mevcut issue/PR'ları kontrol edin.
2. Büyük mimari değişiklikler için önce bir tartışma/RFC açın.
3. Config ve doküman değişiklikleri için PR yeterli; kod katkıları Faz 2
   itibarıyla kabul edilmeye başlanacak.
4. Commit mesajlarında değişikliğin *neden* yapıldığını açıklayın.

## Lisans

[GPL-3.0](LICENSE)
