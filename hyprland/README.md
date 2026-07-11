# hyprland/

Navigator masaüstünün compositor katmanı: [Hyprland](https://hyprland.org) (Wayland).

- `hyprland.conf` — Faz 1 taban yapılandırması: keybind'ler, workspace davranışı,
  pencere yönetimi ve animasyon ayarları.
- Görsel kimlik (`theme/palette.json`) ile senkron tutulan renk değerleri
  (aktif kenarlık gradyanı vb.) burada sabit kodlanmıştır; ileride tema
  dosyalarından otomatik üretilecek şekilde script'e bağlanabilir.
- Super+Space kısayolu, Faz 2'de `ai-stack/router` ile bağlanacak asistan
  paneli için şimdilik placeholder bir komuta işaret ediyor.

## Durum

Faz 1 — statik config taslağı. Henüz test edilmedi, gerçek bir Navigator
oturumunda derlenip denenmedi.
