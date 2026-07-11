# shell/

Navigator'ın özgün masaüstü kabuğu (panel, bildirim merkezi, asistan paneli,
uygulama başlatıcı vb.) burada yaşayacak.

## Planlanan teknoloji

[Quickshell](https://quickshell.outfoxxed.me/) veya [AGS](https://aylur.github.io/ags-docs/)
tabanlı, Hyprland ile doğrudan konuşan özgün bir shell. İkisi arasındaki seçim
Faz 2 başında yapılacak; kriterler: Wayland/Hyprland entegrasyon olgunluğu,
performans, ve `ai-stack/router` ile IPC kolaylığı.

## Kapsam (ileride)

- Üst/alt panel: workspace göstergesi, sistem durumu, saat
- Bildirim merkezi
- AI asistan paneli (Super+Space ile açılan, `hyprland/hyprland.conf` içinde
  şimdilik placeholder olan kısayolun hedefi)
- Uygulama başlatıcı (wofi'nin yerini alacak özgün launcher)

## Durum

Faz 1 — henüz kod yok. Bu klasör yer tutucu olarak duruyor.
