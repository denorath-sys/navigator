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

## Bilinen sınırlama — çalışma zamanında doğrulanmadı

Quickshell, Fedora'ya özel bir COPR paketi (Qt 6.10 gerektiriyor) olduğundan
bu geliştirme ortamında (Debian tabanlı, Qt 6.8.2) kurulamıyor/test
edilemiyor. Dosyalar Quickshell 0.3.0 dokümantasyonuna sadık kalınarak
yazıldı ve temel bir parantez/süslü parantez dengesi kontrolünden geçirildi,
ama gerçek render/çalışma zamanı doğrulaması yapılmadı. Bu, Faz 3'te
Navigator imajı gerçek/sanal donanımda çalıştırıldığında yapılacak.

## Çalıştırma (Faz 3'te, imaj içinde)

```sh
cd shell
qs -p shell.qml
```

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
`Clock.qml`, `WorkspaceIndicator.qml`, `AssistantToggle.qml`). Çalışma
zamanında henüz doğrulanmadı (yukarıya bkz.).
