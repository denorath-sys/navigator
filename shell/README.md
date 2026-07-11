# shell/

Navigator'ın özgün masaüstü kabuğu (panel, bildirim merkezi, asistan paneli,
uygulama başlatıcı vb.) burada yaşayacak.

## Planlanan teknoloji

**Karar (Faz 1 sonu): [Quickshell](https://quickshell.outfoxxed.me/)** — Qt6/QML
tabanlı, Hyprland ile doğrudan konuşan özgün bir shell. AGS/Astal'a (GTK4/GJS)
karşı tercih edildi; gerekçe: QML'in performans/render avantajı ve Navigator'ın
kendine özgü kimliğini sıfırdan, daha az hazır şablona bağımlı kurma tercihi.

Not: Qt6 + QML modülleri kurulumu büyük bir bağımlılık ağacı getirir (200 MB
kısıtı nedeniyle Faz 1'de yerel ortamda kurulmadı) — gerçek implementasyon ve
bağımlılık kurulumu Faz 2'de, GitHub Actions üzerinden doğrulanacak.

## Kapsam (ileride)

- Üst/alt panel: workspace göstergesi, sistem durumu, saat
- Bildirim merkezi
- AI asistan paneli (Super+Space ile açılan, `hyprland/hyprland.conf` içinde
  şimdilik placeholder olan kısayolun hedefi)
- Uygulama başlatıcı (wofi'nin yerini alacak özgün launcher)

## Durum

Faz 1 — henüz kod yok. Bu klasör yer tutucu olarak duruyor.
