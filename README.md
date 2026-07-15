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
  tier→model önerisi, 16 test). `ai-stack/mcp-tools` ilk MCP sunucusunu
  aldı (resmi SDK'sız, stdlib-only stdio JSON-RPC 2.0) ve ardından
  genişletildi: sandbox'lı dosya sistemi araçları (`read_file`/
  `list_directory`/`write_file`/`delete_file`/`rename_file` — path
  traversal engellemeli; yazma için overwrite koruması, silme için
  zorunlu `confirm=true`, yeniden adlandırma için hem kaynak hem hedef
  sandbox kontrolü), klasik HTTP+SSE transport (`GET /sse` +
  `POST /messages`, stdio'ya ek olarak) ve HTTP+SSE için zorunlu Bearer
  token kimlik doğrulaması (otomatik token üretimi, `hmac.compare_digest`
  ile zamanlama saldırısına dayanıklı karşılaştırma — kimliksiz çalışma
  hiçbir zaman mümkün değil), ve salt-okunur Hyprland sorgu araçları
  (`list_windows`/`list_workspaces`/`active_window`, `hyprctl -j` sarmalar
  — bu Debian makinesinde gerçek bir compositor olmadığından mock'lanmış
  + graceful-hata testleriyle doğrulandı, gerçek pencere verisi Faz 3'e
  kaldı) — toplam 88 test, gerçek subprocess/TCP soketleriyle uçtan uca
  doğrulandı. `ai-stack/cloud-bridge`
  kimlik bilgisi/istemci katmanını aldı (Anthropic Claude API, stdlib-only
  ham HTTP, 16 test) ve kullanıcı onayıyla **gerçek bir API key bağlandı**
  (`.env.local`'a yazıldı, `.gitignore` ile hariç tutulmuş — asla commit
  edilmiyor). `ai-stack/router` karar katmanını VE hem `local-runtime` hem
  `cloud-bridge` entegrasyonunu tamamladı (`route` kararına göre ilgili
  modülü subprocess ile gerçekten çağırıyor, 27 test). Kullanıcı onayıyla
  **Ollama kuruldu** (`curl -fsSL https://ollama.com/install.sh | sh`,
  ~1.37 GB) ve **`llama3.2:3b` modeli indirildi** (`ollama pull`, ~2 GB)
  — `route: "local"` artık bu makinede gerçekten uçtan uca çalışıyor,
  gerçek metin üretiyor; **`route: "cloud"` de artık gerçek bir Claude API
  yanıtı üretiyor** (kimlik bilgili testler `.env.local` yoksa/CI'da
  otomatik `skip` olacak şekilde tasarlandı). `ai-stack`'in beş modülünün
  tamamı gerçek: hem yerel hem bulut yolu bu makinede uçtan uca çalışıyor.
  `hyprland/
  hyprland.conf` statik sözdizimi incelemesinden geçti (bu Debian
  geliştirme ortamında Hyprland paketli olmadığından gerçek compositor
  çalıştırılamadı — bkz. `hyprland/README.md`); sözdizimsel hata
  bulunmadı, bir açık nokta (`e+1`/`e-1` mouse-scroll workspace geçişi)
  not edildi. Gerçek runtime doğrulaması Faz 3'e kaldı.
- **Faz 3 — İmaj build & test (ilk gerçek boot testi başarılı):**
  [`build-disk-and-boot-test.yml`](.github/workflows/build-disk-and-boot-test.yml)
  eklendi — `ghcr.io`'ya push edilmiş Navigator imajını `bootc-image-builder`
  ile gerçek bir qcow2 disk imajına çevirir, sonra GitHub Actions
  runner'ının KVM'i (ücretsiz `ubuntu-24.04` runner'larda 2024'ten beri
  `/dev/kvm` var) ile bu disk imajını GERÇEKTEN boot edip SSH üzerinden
  doğrular. Üç gerçek CI hatası bulunup düzeltildi (`customizations.user`
  şemasında yanlış alan adı; ublue tabanlı imajların konteyner içinde
  varsayılan kök dosya sistemini bildirmemesi, `--rootfs btrfs` ile
  çözüldü; Ubuntu 24.04'ün `ovmf` paketinin dosya adlarını değiştirmesi).
  Dördüncü çalıştırmada **gerçek bir VM gerçekten boot etti**: disk build
  19 dakika sürdü, VM SSH üzerinden erişilebilir hale geldi, `/etc/os-release`
  gerçek imajı doğruladı (`Fedora Linux 43.20260710.0`,
  `OSTREE_VERSION='43.20260710.0'`), `systemctl is-system-running` →
  `degraded` döndü (tek başarısız unit: sanal ortamda beklenen
  `mcelog.service` — gerçek donanım MCE register'ları gerektirir, VM'de
  yok, zararsız). Manuel tetiklemeyle (`workflow_dispatch`) çalışır —
  `build-image.yml`'nin aksine her push'ta otomatik çalışmaz. Bu,
  `hyprland.conf`'un statik incelemesinin ve `mcp-tools`'un Hyprland sorgu
  araçlarının ilk kez gerçek bir Fedora Atomic ortamında (kısmen —
  GUI/compositor değil, temel sistem boot'u) doğrulandığı adım. **Gerçek
  bir Hyprland compositor oturumunu bu VM'de çalıştırıp `mcp-tools`'un
  Hyprland araçlarını gerçek pencere verisiyle test etmek** araştırıldı
  (QEMU `virtio-gpu-pci` ile teknik olarak mümkün görünüyor, bkz.
  `ai-stack/mcp-tools/README.md` "Hyprland araçları") ama zincir uzun ve
  her CI denemesi ~20 dakika sürdüğünden kullanıcı kararıyla bilinçli
  olarak Faz 4/5'e ertelendi.
- **Faz 4 — AI stack tamamlama (başladı):** `ai-stack/assistant` eklendi
  — `router`, `mcp-tools` ve `cloud-bridge`'i tek bir gerçek konuşma
  döngüsünde birleştiren bir CLI/REPL (Quickshell UI'ı beklemeden, bu
  makinede gerçekten test edilebilecek bir ilk adım olarak). `router`'a
  `--decide-only` (sadece karar, çalıştırmaz), `cloud-bridge`'e
  `--converse`/`send_messages()` (çok turlu mesaj + tool-use) eklendi.
  **Gerçek bir tool-use döngüsü uçtan uca doğrulandı:** karmaşık bir
  donanım sorusuna Claude gerçekten `mcp-tools`'un `hardware_tier`
  aracını çağırıp bu makinenin gerçek verileriyle (6 çekirdek, 15.4 GB
  RAM, ayrık GPU yok) doğru cevap verdi. **Dürüstçe belgelenen gerçek bir
  sınırlama:** yerel yolda (Ollama) henüz araç kullanımı yok — kısa/basit
  istekler yerele düşüp gerçek veri yerine genel/hatalı cevap üretebiliyor,
  bu gizlenmedi (bkz. `ai-stack/assistant/README.md`). Kalan: gerçek
  Hyprland/Quickshell compositor testi (Faz 3'ten ertelendi), UI entegrasyonu.
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
  ([`build-image.yml`](.github/workflows/build-image.yml),
  [`build-disk-and-boot-test.yml`](.github/workflows/build-disk-and-boot-test.yml)),
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
