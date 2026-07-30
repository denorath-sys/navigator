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
  — `router`, `mcp-tools`, `local-runtime` ve `cloud-bridge`'i tek bir
  gerçek konuşma döngüsünde birleştiren bir CLI/REPL (Quickshell UI'ı
  beklemeden, bu makinede gerçekten test edilebilecek bir ilk adım
  olarak). `router`'a `--decide-only` (sadece karar, çalıştırmaz),
  `cloud-bridge`'e VE `local-runtime`'a `--converse` (çok turlu mesaj +
  tool-use) eklendi. **Hem cloud hem local'de gerçek bir tool-use
  döngüsü uçtan uca doğrulandı:** karmaşık bir donanım sorusuna hem
  Claude hem yerel `llama3.2:3b` gerçekten `mcp-tools`'un `hardware_tier`
  aracını çağırıp bu makinenin gerçek verileriyle (6 çekirdek, 15.4 GB
  RAM, ayrık GPU yok) doğru cevap verdi. **Gerçek testte yakalanan ve
  düzeltilen bir güvenlik riski:** yerel (3B) model, zararsız bir "sadece
  merhaba de" isteğinde bile kendiliğinden `write_file`'ı
  `overwrite=true` ile çağırmaya kalkıştı — bu, "sistemi değiştiren her
  eylem açık onay ister" ilkesinin gerçek bir ihlal riskiydi. Düzeltme:
  yazma/silme/yeniden adlandırma araçları yerel modele artık hiç
  gösterilmiyor, sadece salt-okunur erişimi var; gösterilmese de
  halüsinasyonla çağrılırsa ayrı bir savunma katmanı reddediyor. Yerel
  modelin kalan gerçek güvenilirlik sınırlaması (ara sıra gereksiz araç
  çağırma/ham JSON metni üretme) gizlenmeden belgelendi (bkz.
  `ai-stack/assistant/README.md`). **Konuşma geçmişi/hafıza eklendi**:
  REPL'de bellekte (`/reset` ile temizlenir), `--history-file` ile ayrı
  süreçler arasında bile kalıcı. **Router'a "araç gerekebilir mi" sinyali
  eklendi**: karmaşıklık sezgisi artık sadece kelime sayısına değil,
  donanım/dosya/pencere ile ilgili anahtar kelimelere de bakıyor — kısa
  ama araç gerektiren istekler (ör. "kaç CPU çekirdeği var?") bu makinede
  (tier="low") artık otomatik olarak daha güvenilir bulut yoluna
  düşüyor, gerçek testte doğrulandı. **Gerçek Hyprland compositor testi
  tamamlandı** (Faz 3'ten ertelenmişti): `build-disk-and-boot-test.yml`'e
  eklenen `hyprland-test` job'ı, gerçek bir Navigator disk imajını
  QEMU'da (`virtio-gpu-pci` + `-display vnc`, host'ta GPU/EGL
  gerektirmez) boot edip Hyprland'ı gerçekten başlatıyor ve
  `mcp-tools`'un Hyprland sorgu araçlarını gerçek bir compositor'a karşı
  çağırıyor. Yolda iki gerçek sorun bulunup düzeltildi: Hyprland'ın
  kasıtlı root reddi (`--i-am-really-stupid` bayrağı gerekti) ve
  aquamarine'ın DRM backend'inin `libseat` üzerinden bir seat açmaya
  çalışması (SSH oturumunun gerçek bir seat'i yok; imaja eksik olan
  `seatd` paketi eklendi, test betiği Hyprland'dan önce seatd'yi
  başlatıp `LIBSEAT_BACKEND=seatd` ayarlıyor). Sonuç: gerçek
  `hyprctl monitors` bir "Virtual-1" (QEMU) monitörü gösterdi;
  `list_windows`, `list_workspaces` VE `active_window`'un üçü de gerçek
  JSON döndürdü — mock değil (bkz. `ai-stack/mcp-tools/README.md`
  "Hyprland araçları"). **`hyprland.conf`'un kendisi de aynı VM'de gerçek
  compositor'a yüklendi:** şimdiye kadar sadece statik sözdizimi
  incelemesinden geçmişti (bkz. `hyprland/README.md`), artık CI'da
  gerçekten parse edilip `hyprctl getoption`/`hyprctl binds` ile
  varsayılandan farklı beş değerin (border_size, rounding, blur:passes,
  resize_on_border, touchpad:natural_scroll) ve mainMod+RETURN→kitty
  bind'inin gerçekten etkili olduğu doğrulandı, hiç config hatası
  bulunmadı. **Quickshell'in kendisi de aynı VM'de gerçek Hyprland'a
  karşı çalıştırıldı:** şimdiye kadar sadece statik `qmllint`
  incelemesinden geçmişti (bkz. `shell/README.md`), artık `qs -p
  shell.qml` CI'da gerçekten başlıyor ve `Bar.qml` gerçek bir
  layer-shell yüzeyi olarak (`hyprctl layers` ile doğrulanan,
  `namespace: quickshell`, gerçek monitör genişliğinde) map ediliyor —
  ilk gerçek uçtan uca compositor+shell testi. **`AssistantToggle` artık
  `ai-stack/router`'a gerçekten bağlı:** yeni `AssistantPanel.qml`,
  `Quickshell.Io.Process` ile `python3 -m router`'ı gerçekten subprocess
  olarak çağırıyor; `shell.qml`'deki `IpcHandler` hem panel tıklamasını
  hem Hyprland Super+Space'i (artık `qs ipc call assistant toggle`,
  eskiden placeholder `echo`) aynı panele bağlıyor. CI'da uçtan uca
  doğrulandı — gerçek yanıt: `[cloud] unavailable:
  credentials_not_configured` (CI'da Ollama/Claude kimlik bilgisi yok,
  bu yüzden router her zaman cloud'a düşüyor ve cloud-bridge graceful
  "unavailable" dönüyor — mock değil, gerçek bir uçtan uca hata yolu).
  Yol boyunca iki gerçek sorun bulunup düzeltildi: `qs ipc call`'ın
  `-p` bayrağının `ipc` alt komutuna (`call`'a değil) kayıtlı olması,
  ve `ai-stack/router`'ın kendi bağımlılığı `ai-stack/hardware-probe`'un
  CI'a hiç kopyalanmamış olması (bkz. `shell/README.md` "AssistantPanel
  — gerçek ai-stack/router entegrasyonu"). **`ai-stack` artık imajın
  gerçek bir katmanı:** `image/Containerfile` Katman 5 (bugüne kadar
  PLACEHOLDER) altı modülü `/usr/share/navigator/ai-stack/` altına
  kopyalıyor ve build sırasında `compileall --invalidation-mode
  checked-hash` ile bytecode üretiyor (ostree mtime'ları normalize
  ettiği için timestamp tabanlı .pyc'ler salt-okunur `/usr`'da her
  çağrıda yeniden derlenirdi — yerel `python3 -v` deneyiyle doğrulandı,
  bkz. `ai-stack/README.md` "İmajdaki kurulum yolu"). Böylece CI'daki
  scp + `rpm-ostree usroverlay` taklidi kaldırıldı: `hyprland-test`
  artık `/usr` salt-okunur haldeyken imajın kendi içeriğini doğruluyor.
  Kalan: görsel doğruluk, gerçek Hyprland IPC, Ollama'nın imaja
  katmanlanması (Katman 6, hâlâ PLACEHOLDER).
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
