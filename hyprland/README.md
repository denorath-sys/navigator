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

**O zamanki sınırlama (artık geçerli değil):** Bu statik bir inceleme,
gerçek compositor çalıştırılmadı — runtime doğrulaması Faz 3'e
bırakılmıştı. Aşağıya bkz.

## Faz 4 — gerçek compositor'da runtime doğrulaması (CI)

`.github/workflows/build-disk-and-boot-test.yml`'deki `hyprland-test`
job'ı artık bu dosyayı (`hyprland.conf`) gerçek bir Navigator disk
imajında, gerçek bir Hyprland compositor'a **gerçekten yüklüyor**
(`/root/.config/hypr/hyprland.conf`'a kopyalanıp Hyprland'ın varsayılan
arama yolundan okunuyor) — statik inceleme değil, çalışan bir compositor.

Doğrulama, config'teki Hyprland'ın kendi varsayılanlarından **farklı**
değerlerin gerçekten etkili olup olmadığını `hyprctl getoption -j` ile
kontrol ederek yapılıyor (varsayılanlar Hyprland kaynağında —
`ConfigValues.cpp` — doğrulandı, böylece eşleşme tesadüf değil):

| Ayar | Varsayılan | `hyprland.conf` | CI'da gerçek sonuç |
|---|---|---|---|
| `general:border_size` | 1 | 2 | ✅ 2 |
| `decoration:rounding` | 0 | 10 | ✅ 10 |
| `decoration:blur:passes` | 1 | 2 | ✅ 2 |
| `general:resize_on_border` | false (0) | true | ✅ 1 |
| `input:touchpad:natural_scroll` | false (0) | true | ✅ 1 |

Ayrıca `hyprctl binds -j` ile `$mainMod, RETURN, exec, $terminal`
bind'inin gerçekten yüklendiği (RETURN tuşu → `kitty` çalıştırma)
doğrulandı, ve `/root/hyprland.log`'da hiçbir "config error"/"syntax
error" satırı bulunmadı.

**Bilinen kalan sınırlama:** Bu, config'in *parse edilip uygulandığının*
kanıtı — gerçek klavye/fare girdisiyle bind'lerin fiilen tetiklendiği
(ör. gerçekten Süper+Enter'a basıp kitty'nin açıldığı) veya görsel
render'ın (blur/shadow/animasyon) doğru göründüğü ayrıca test edilmedi;
VNC display üzerinden headless bir CI koşusunda bu, ek karmaşıklık
gerektirir ve şimdilik gerekli görülmedi.

## Durum

Faz 2 — statik sözdizimi incelemesinden geçti. Faz 4'te CI'da gerçek bir
Hyprland compositor'a **gerçekten yüklendi ve doğrulandı** (yukarıya
bkz.) — artık sadece statik bir inceleme değil.
