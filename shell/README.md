# shell/

Navigator'ın özgün masaüstü kabuğu (panel, bildirim merkezi, asistan paneli,
uygulama başlatıcı vb.) burada yaşıyor.

## Teknoloji

**[Quickshell](https://quickshell.outfoxxed.me/)** (Qt6/QML) — Hyprland ile
doğrudan konuşan özgün bir shell. AGS/Astal'a (GTK4/GJS) karşı tercih
edildi; gerekçe: QML'in performans/render avantajı ve Navigator'ın kendine
özgü kimliğini sıfırdan, daha az hazır şablona bağımlı kurma tercihi.
İmaja kurulumu `image/Containerfile` Katman 2'de tanımlı
(`errornointernet/quickshell` COPR, Fedora'ya özel).

## Dosyalar

- `shell.qml` — Quickshell giriş noktası (`ShellRoot`)
- `Theme.qml` — Navigator marka paleti (`../theme/palette.json` ile manuel
  senkron tutulur, `hyprland/hyprland.conf`'un renk senkron yöntemiyle aynı)
- `Bar.qml` — üst panel (`PanelWindow`, wlr-layer-shell)
- `WorkspaceIndicator.qml` — workspace göstergesi (**placeholder**: statik
  1-10 pil, henüz gerçek Hyprland IPC'siyle bağlı değil)
- `AssistantToggle.qml` — AI asistan paneli anahtarı (**placeholder**: sadece
  görsel buton, henüz `ai-stack/router`'a bağlı değil)
- `Clock.qml` — canlı saat göstergesi

## Gerçek compositor'da runtime doğrulaması (CI, Faz 4)

Quickshell, Fedora'ya özel bir COPR paketi (Qt 6.10 gerektiriyor) olduğundan
bu geliştirme ortamında (Debian tabanlı, Qt 6.8.2) hâlâ kurulamıyor —
ama artık CI'da gerçek bir compositor'a karşı doğrulanıyor.

`.github/workflows/build-disk-and-boot-test.yml`'deki `hyprland-test`
job'ı, Hyprland gerçekten başladıktan sonra bu dizini VM'e kopyalayıp
`qs -p /root/shell/shell.qml` ile gerçekten başlatıyor (Hyprland'ın
oluşturduğu gerçek Wayland soketine `WAYLAND_DISPLAY` üzerinden
bağlanarak) ve sadece "süreç çökmedi" değil, `hyprctl layers -j` ile
`Bar.qml`'in (`PanelWindow`, wlr-layer-shell) gerçekten bir yüzey map
ettiğini doğruluyor. Gerçek sonuç:

```
INFO: Configuration Loaded
```
```
Layer level 2 (top):
    Layer 55b9230bbd30: xywh: 0 20 1280 32, namespace: quickshell, pid: 1516
```

(`w=1280` gerçek monitör genişliğiyle, `h=32` `Theme.qml`'deki
`barHeight`'la birebir eşleşiyor — mock değil, gerçek render.) İki
zararsız uyarı görüldü: `libEGL warning: egl: failed to create dri2
screen` (virtio-gpu'nun yazılım-only olması bekleniyor, render'ı
engellemedi).

**Bilinen kalan sınırlama:** Bu, `Bar.qml`'in gerçekten map olup
render edildiğinin kanıtı — görsel çıktının (renkler, blur, layout)
piksel piksel doğru olduğu veya `WorkspaceIndicator`/`AssistantToggle`
içindeki tıklama/etkileşimin çalıştığı ayrıca test edilmedi (headless
VNC display'den ekran görüntüsü almak ek karmaşıklık gerektirir).

**Gerçek statik analiz yapıldı (compositor gerektirmez):** Bu makineye
`qt6-declarative-dev-tools` kuruldu ve gerçek Qt6 `qmllint`'i altı QML
dosyasının tamamına karşı çalıştırıldı:

- `Theme.qml`, `Clock.qml`, `AssistantToggle.qml` — **temiz**, hiç uyarı yok.
- `WorkspaceIndicator.qml` — qmllint gerçek bir sorun buldu: `Repeater`
  delegate'i içinde dıştaki `theme` id'sine niteliksiz (unqualified)
  erişim (`[unqualified]`). `pragma ComponentBehavior: Bound` eklenerek
  düzeltildi, şimdi **temiz**.
- `shell.qml`, `Bar.qml` — Quickshell'in QML plugin'i Debian'da paketli
  olmadığından `import Quickshell` çözümlenemiyor; bu, `ShellRoot`/
  `PanelWindow` ve onların özel property'leri (`anchors`,
  `implicitHeight` vb.) için beklenen kaskad "unresolved" uyarılarına
  yol açıyor — gerçek bir kod hatası değil, sadece yerel ortamda
  Quickshell tip tanımlarının eksik olması. Bu iki dosyanın Quickshell'e
  özgü kısımları hâlâ doğrulanamıyor.

Bu, "sadece parantez dengesi kontrolü"nden gerçek bir adım ileri: dört
dosya artık gerçek bir Qt6 derleyici/linter'ından geçti, kalan iki
dosyanın da Quickshell dışı kısımları (import'lar, genel QML sözdizimi)
doğrulandı. Gerçek çalışma zamanı/render doğrulaması artık CI'da yapılıyor
(yukarıya bkz.) — kalan sınırlama sadece görsel piksel doğruluğu ve
etkileşim testleri.

## Çalıştırma (Faz 3'te, imaj içinde)

```sh
cd shell
qs -p shell.qml
```

## Statik analiz (şimdi, herhangi bir Qt6 ortamında)

```sh
cd shell
for f in *.qml; do qt6-qmllint "$f" || /usr/lib/qt6/bin/qmllint "$f"; done
```

(Paket adı dağıtıma göre değişir — Debian/Pardus'ta `qt6-declarative-dev-tools`,
Fedora'da `qt6-qtdeclarative-devel` benzeri.)

## Kapsam (ileride)

- ~~Üst panel: workspace göstergesi, saat~~ — ilk taslak hazır (placeholder
  workspace göstergesi ile)
- Alt panel / bildirim merkezi
- AI asistan paneli — gerçek implementasyon (şu an sadece buton placeholder'ı
  var, `hyprland/hyprland.conf`'taki Super+Space kısayoluna henüz bağlı değil)
- Uygulama başlatıcı (wofi'nin yerini alacak özgün launcher)
- Gerçek Hyprland IPC entegrasyonu (aktif/dolu workspace tespiti)

## Durum

Faz 2 — ilk QML dosyaları yazıldı (`shell.qml`, `Theme.qml`, `Bar.qml`,
`Clock.qml`, `WorkspaceIndicator.qml`, `AssistantToggle.qml`). Gerçek
Qt6 `qmllint` ile statik analiz yapıldı — dördü tamamen temiz, biri
(`WorkspaceIndicator.qml`) gerçek bir uyarı (unqualified id erişimi)
bulunup `pragma ComponentBehavior: Bound` ile düzeltildi, ikisi
(`shell.qml`, `Bar.qml`) Quickshell dışı kısımlarıyla doğrulandı.
Faz 4'te CI'da gerçek bir Hyprland compositor'a karşı çalıştırıldı:
`qs -p shell.qml` gerçekten başladı ve `Bar.qml` gerçek bir
layer-shell yüzeyi olarak map edildi (`hyprctl layers` ile doğrulandı)
— bkz. yukarıdaki "Gerçek compositor'da runtime doğrulaması" bölümü.
Kalan: görsel piksel doğruluğu, gerçek Hyprland IPC (workspace/pencere
verisi), tıklama/etkileşim testleri.
