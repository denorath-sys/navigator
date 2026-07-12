# hyprland/

Navigator masaüstünün compositor katmanı: [Hyprland](https://hyprland.org) (Wayland).

- `hyprland.conf` — Faz 1 taban yapılandırması: keybind'ler, workspace davranışı,
  pencere yönetimi ve animasyon ayarları.
- Görsel kimlik (`theme/palette.json`) ile senkron tutulan renk değerleri
  (aktif kenarlık gradyanı vb.) burada sabit kodlanmıştır; ileride tema
  dosyalarından otomatik üretilecek şekilde script'e bağlanabilir.
- Super+Space kısayolu, Faz 2'de `ai-stack/router` ile bağlanacak asistan
  paneli için şimdilik placeholder bir komuta işaret ediyor.

## Faz 2 — statik sözdizimi incelemesi

Geliştirme ortamı Debian/Pardus tabanlı olduğundan (Hyprland bu dağıtımda
paketli değil) gerçek bir Hyprland compositor oturumunda çalıştırılamadı —
bunun yerine `hyprland.conf`, Hyprland'ın belgelenmiş `hyprlang` söz
dizimine göre satır satır statik olarak incelendi:

- Süslü parantez dengesi otomatik kontrol edildi: **OK**
- `general`, `decoration` (iç içe `blur`/`shadow`), `animations`, `dwindle`,
  `input` (iç içe `touchpad`), `gestures` blokları güncel Hyprland söz
  dizimine uygun
- Değişkenler (`$mainMod`, `$terminal` vb.) kullanılmadan önce tanımlı —
  sıralama doğru (Hyprlang basit metin ikamesi yapar)
- Tüm `bind`/`bindm` satırları geçerli dispatcher isimleri kullanıyor

**Sonuç:** Sözdizimsel bir hata bulunamadı.

**Açık bir not:** `mouse_down`/`mouse_up` ile workspace geçişi `e+1`/`e-1`
kullanıyor (satır 154-155) — bu, "sıradaki workspace" değil "bir sonraki/
önceki **boş** workspace'e git" anlamına gelir. Sıralı geçiş kastedilmişse
`+1`/`-1` olarak değiştirilmesi gerekebilir; şu an kasıtlı mı yoksa
düzeltilmesi mi gerekiyor netleşmedi, olduğu gibi bırakıldı.

**Sınırlama:** Bu statik bir inceleme, gerçek compositor çalıştırılmadı —
runtime doğrulaması (keybind çakışmaları, gerçek hatalar) Faz 3'te
gerçek/sanal Fedora ortamında (Navigator imajı üzerinde) yapılacak.

## Durum

Faz 2 — statik sözdizimi incelemesinden geçti (yukarıya bkz.). Gerçek bir
Hyprland compositor oturumunda henüz çalıştırılmadı/derlenmedi — bu Faz
3'e kaldı.
