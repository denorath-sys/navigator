# hyprland/

Navigator masaüstünün compositor katmanı: [Hyprland](https://hyprland.org) (Wayland).

- `hyprland.conf` — Faz 1 taban yapılandırması: keybind'ler, workspace davranışı,
  pencere yönetimi ve animasyon ayarları.
- Görsel kimlik (`theme/palette.json`) ile senkron tutulan renk değerleri
  (aktif kenarlık gradyanı vb.) burada sabit kodlanmıştır; ileride tema
  dosyalarından otomatik üretilecek şekilde script'e bağlanabilir. Bu
  tekrar artık **CI'da gerçekten doğrulanıyor** — imajdaki
  `hyprland.conf`'un `col.active_border` gradyanı/açısı ve `shadow`
  rengi, imajdaki `palette.json` ile karşılaştırılıyor (aşağıya bkz.).
- Super+Space kısayolu Faz 4'te `ai-stack/router`'a gerçekten bağlandı
  (`qs ipc call assistant toggle` → `shell/AssistantPanel.qml`).
- `exec-once` ile otomatik başlatma (aşağıya bkz.).

## Otomatik başlatma (`exec-once`)

Bu dosyada uzun süre hiç `exec-once` yoktu — imajda bulunan bileşenleri
hiçbir şey başlatmıyordu. Katman 7 ile shell imaja girdikten sonra iki
giriş eklendi:

| Komut | Neden |
|---|---|
| `qs -p /usr/share/navigator/shell/shell.qml` | Navigator shell (Katman 7'nin koyduğu yol) |
| `/usr/libexec/polkit-mate-authentication-agent-1` | Ajan yoksa GUI'den yetki isteyen işlemler kullanıcıya hiç sorulmadan sessizce reddedilir |

**Bilinçli olarak eklenmeyenler**, gerekçeleriyle config'in içinde de
yazılı:

- **waybar** — Navigator'ın kendi üst paneli var (`shell/Bar.qml`); ikisi
  birlikte çalışırsa iki panel üst üste biner.
- **hyprpaper, hypridle** — ikisi de kendi config dosyasını gerektiriyor
  ve Navigator henüz ikisini de yazmadı (duvar kağıdı varlığı da yok).
  Config'siz başlatmak ilk saniyede pes eden bir daemon demek olurdu.
- **NetworkManager, pipewire, wireplumber** — systemd tarafından
  yönetiliyorlar (sistem servisi ve socket ile tetiklenen kullanıcı
  servisleri), compositor'ın işi değil.

### `exec-once` hedefleri CI'da doğrulanıyor

Yanlış yazılmış ya da paket değişimiyle kaybolmuş bir `exec-once`'ı
Hyprland **sessizce yutar**: compositor yine açılır, sadece masaüstü
eksik başlar ve hiçbir test kırılmaz. Bu yüzden CI, imajdaki
`hyprland.conf`'tan `exec-once` satırlarını ayrıştırıp her hedefin
imajda gerçekten çalıştırılabilir olduğunu kontrol ediyor.

Ayrıca Quickshell artık CI'da **elle başlatılmıyor** — Hyprland'ın kendi
`exec-once`'ı başlatıyor ve test bunu doğruluyor. (Elle de başlatılsaydı
ikinci bir örnek olur, `qs ipc` çağrılarının hangi örneğe gittiği
belirsizleşirdi.)

## İmajdaki kurulum yolu (Katman 4)

`image/Containerfile` Katman 4, bu dosyayı imaja
`/etc/skel/.config/hypr/hyprland.conf` olarak koyuyor. `useradd` yeni bir
hesap açarken `/etc/skel`'i ev dizinine kopyaladığı için her yeni
Navigator kullanıcısı bu config ile başlıyor; sonrasında kendi
`~/.config/hypr/hyprland.conf`'unu serbestçe değiştirebiliyor ve imaj
güncellemeleri bu dosyayı **ezmiyor** (`/etc/skel` yalnızca hesap
oluşturma anında okunur).

Bu mekanizmanın bootc-image-builder'ın oluşturduğu hesaplarda gerçekten
işlediği varsayılmadı, ölçüldü: CI önce teşhis olarak sordu
([run 30664668160](https://github.com/denorath-sys/navigator/actions/runs/30664668160)),
gerçek cevap alındı — `navtest`'in ev dizini `/var/home/navtest` (ostree
düzeni) ve içinde `.bashrc`/`.bash_profile` ile birlikte
`.config/hypr/hyprland.conf` var, `/etc/skel`'dekiyle birebir aynı.
Ölçüm kesin olduğu için kontrol artık **iddia**: bib veya taban imaj bu
davranışı değiştirirse test kırılır.

## Faz 2 — statik sözdizimi incelemesi

Geliştirme ortamı Debian/Pardus tabanlı olduğundan (Hyprland bu dağıtımda
paketli değil) gerçek bir Hyprland compositor oturumunda çalıştırılamadı —
bunun yerine `hyprland.conf`, Hyprland'ın belgelenmiş `hyprlang` söz
dizimine göre satır satır statik olarak incelendi:

- Süslü parantez dengesi otomatik kontrol edildi: **OK**
- `general`, `decoration` (iç içe `blur`/`shadow`), `animations`, `dwindle`,
  `input` (iç içe `touchpad`) blokları güncel Hyprland söz dizimine uygun
- ⚠️ **`gestures` bloğu hakkındaki bu değerlendirme YANLIŞTI** — aşağıya
  bkz. "Statik incelemenin kaçırdığı gerçek hata"
- Değişkenler (`$mainMod`, `$terminal` vb.) kullanılmadan önce tanımlı —
  sıralama doğru (Hyprlang basit metin ikamesi yapar)
- Tüm `bind`/`bindm` satırları geçerli dispatcher isimleri kullanıyor

**Sonuç:** Sözdizimsel bir hata bulunamadı — **ama bu sonuç eksikti.**

## Statik incelemenin kaçırdığı gerçek hata

`gestures { workspace_swipe = true }` sözdizimsel olarak kusursuzdu ve
Hyprland belgelerinde yıllarca böyleydi. Ama **Hyprland 0.51 jest
sistemini baştan yazdı ve bu seçeneği kaldırdı**; imajdaki sürüm
(0.51.1) onu görünce gerçek bir config hatası üretiyordu:

```
Config error in file /var/roothome/.config/hypr/hyprland.conf at line 113:
config option <gestures:workspace_swipe> does not exist.
```

Bu hata kullanıcının ekranında **kırmızı bir hata afişi** olarak
duruyordu. Yakalanmasının hiçbir yolu olmadığı için değil — üç ayrı
kontrol vardı ve üçü de sessiz kaldı:

1. Statik sözdizimi incelemesi: hyprlang'a göre geçerli, seçeneğin var
   olup olmadığını bilmesi mümkün değil.
2. CI'daki `hyprctl getoption` kontrolleri: sadece beş belirli seçeneği
   soruyordu, hatalı olan onların arasında değildi.
3. CI'daki `grep -i "config error" /root/hyprland.log`: **"(yok)" bastı**
   — yani yanlış güvence verdi. Hyprland bu hatayı o log'a o ifadeyle
   yazmıyor.

Ortaya çıkaran şey **görsel doğruluk testinin ilk ekran görüntüsü**
oldu: afiş ekranın tepesinde duruyordu. Ders, bu projede genel olarak
geçerli: bir bileşenin çıktısı görselse, metinsel kontroller "sessiz
kaldı" diye doğru çalıştığını göstermez.

Düzeltme iki parçalı: config'te yeni sözdizimi
(`gesture = 3, horizontal, workspace`), ve CI'daki işe yaramaz log
grep'i yerine compositor'a doğrudan soran gerçek bir iddia
(`hyprctl configerrors`).

**Ve o iddia ilk denemede yanlış yazıldı** — aynı hataya bir kez daha
düşerek: çıktı biçimi ÖLÇÜLMEDEN "no errors" dizgesi bekleniyordu.
Hyprland 0.51 temiz durumda hiçbir şey basmıyor (boş çıktı), dolayısıyla
config düzeltilmiş olmasına rağmen kontrol kırmızı yandı. Kural artık
ölçüme dayanıyor: **boş VEYA "no errors" = temiz.**

Bu sefer kontrolün boş yeşil olmadığı da aynı run içinde kanıtlanıyor:
config'e bilerek var olmayan bir seçenek eklenip `hyprctl reload`
yapılıyor, `configerrors`'ın gerçekten konuştuğu doğrulanıyor, sonra
geri alınıp temizliği yeniden kontrol ediliyor. "Boş çıktı = temiz"
kuralı bu kendi kendini sınama olmadan, komut hiç çalışmasa bile yeşil
kalırdı.

**Açık bir not:** `mouse_down`/`mouse_up` ile workspace geçişi `e+1`/`e-1`
kullanıyor (satır 184-185) — bu, "sıradaki workspace" değil "bir sonraki/
önceki **boş** workspace'e git" anlamına gelir. Sıralı geçiş kastedilmişse
`+1`/`-1` olarak değiştirilmesi gerekebilir; şu an kasıtlı mı yoksa
düzeltilmesi mi gerekiyor netleşmedi, olduğu gibi bırakıldı.

**O zamanki sınırlama (artık geçerli değil):** Bu statik bir inceleme,
gerçek compositor çalıştırılmadı — runtime doğrulaması Faz 3'e
bırakılmıştı. Aşağıya bkz.

## Faz 4 — gerçek compositor'da runtime doğrulaması (CI)

`.github/workflows/build-disk-and-boot-test.yml`'deki `hyprland-test`
job'ı artık bu dosyayı (`hyprland.conf`) gerçek bir Navigator disk
imajında, gerçek bir Hyprland compositor'a **gerçekten yüklüyor** —
statik inceleme değil, çalışan bir compositor.

Katman 4'ten beri test edilen dosya **imajın kendi dosyası**: daha önce
runner'dan VM'e `scp` ile kopyalanıyordu (bir "CI taklidi"), şimdi
`/etc/skel/.config/hypr/hyprland.conf` içinden `/root/.config/hypr/`'a
alınıyor (test root olarak çalışıyor; `/etc/skel` sadece yeni hesaplara
kopyalandığından root için elle almak gerekiyor). Ayrı bir adım imajdaki
dosyanın repodakiyle **birebir aynı** olduğunu da doğruluyor — yani imaj
bayatsa test yeşil kalmıyor.

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
