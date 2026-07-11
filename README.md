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
| Shell | [Quickshell](https://quickshell.outfoxxed.me/) (Qt6/QML) tabanlı özgün kabuk — [`shell/`](shell/) |
| AI Stack | Donanıma göre otomatik model tier seçimi, MCP tabanlı araç erişimi, yerel↔bulut hibrit router — [`ai-stack/`](ai-stack/) |
| Tema | Marka renk paleti + GTK/Qt tema — [`theme/`](theme/) |

Detaylı mimari doküman: [`docs/architecture.md`](docs/architecture.md).

## Yol haritası

- **Faz 1 — İskelet (tamamlandı):** Repo yapısı, config/doküman taslakları,
  CI pipeline tanımı. Yerel ortamda büyük indirme yapılmadı; Containerfile
  GitHub Actions üzerinde build edilip `ghcr.io/denorath-sys/navigator`'a
  push edilerek doğrulandı (base image: `ublue-os/base-main:43` +
  `solopasha/hyprland` COPR). Shell teknolojisi olarak Quickshell seçildi.
- **Faz 2 — Yerel prototip (devam ediyor):** `ai-stack/hardware-probe` ilk
  implementasyonu tamamlandı (Python, stdlib-only, 20 test, gerçek donanımda
  doğrulandı). Quickshell `image/Containerfile`'a eklendi ve build doğrulandı
  (`errornointernet/quickshell` COPR). İlk QML shell dosyaları yazıldı
  (`shell/shell.qml`, `Bar.qml`, `Theme.qml` vb. — henüz çalışma zamanında
  test edilmedi, bkz. `shell/README.md`). `ai-stack/local-runtime`
  orkestrasyon/istemci katmanı tamamlandı (Ollama REST istemcisi,
  tier→model önerisi, 15 test) — Ollama kurulumu ve model indirme ayrı
  bir onay bekliyor. `ai-stack/router` karar katmanı tamamlandı (yerel/bulut
  yönlendirme mantığı, 17 test). `ai-stack/mcp-tools` ilk MCP sunucusunu
  aldı (resmi SDK'sız, stdlib-only stdio JSON-RPC 2.0, 16 test) — dört
  modül (`hardware-probe` → `local-runtime` → `router` → `mcp-tools`)
  artık gerçek MCP protokolü üzerinden uçtan uca çalışıyor. `ai-stack/
  cloud-bridge` kimlik bilgisi/istemci katmanını aldı (Anthropic Claude API,
  stdlib-only ham HTTP, 14 test) — `ai-stack`'in beş modülünün tamamı en az
  bir implementasyon aşamasına ulaştı. Sırada: gerçek Hyprland oturumunda
  config testi; `router`↔`cloud-bridge` entegrasyonu.
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
