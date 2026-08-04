# theme/

Navigator'ın görsel kimliği: pusula, deniz feneri, Orion takımyıldızı ve
Kuzey Yıldızı temalı nautical/gökyüzü estetiği.

## İçerik

- `palette.json` — Marka renk paleti (teal `#4fd1c5`, mor `#8b7cf6`,
  altın `#e8d9a8`, lacivert taban `#0b0f1a`) ve gradyan tanımları.
  `hyprland/hyprland.conf` ile manuel senkron tutulur.
- `gtk/` — GTK3/GTK4 tema varlıkları için yer tutucu (Faz 2).
- `qt/` — Qt5/Qt6 (qt5ct/qt6ct) tema varlıkları için yer tutucu (Faz 2).

## İmajdaki kurulum yolu (Katman 3)

`image/Containerfile` Katman 3, buradan imaja **sadece `palette.json`**'u
alıyor → `/usr/share/navigator/theme/palette.json`. `gtk/` ve `qt/` hâlâ
boş iskelet (içlerinde yalnızca `.gitkeep`) olduğundan katmanlanmıyor:
boş dizinleri imaja koymak, olmayan bir GTK/Qt temasının varmış gibi
görünmesine yol açardı.

### Renk tekrarı artık gerçekten doğrulanıyor

`palette.json` makine-okunur tek kaynak, ama aynı hex değerleri
`hyprland/hyprland.conf` ve `shell/Theme.qml` içinde **elle** tekrar
ediliyor. Bu sessizce sapabilecek bir tekrardı; CI artık her koşuda
karşılaştırıyor (`build-disk-and-boot-test.yml`, "Katman 3/4/7" adımı):

- `col.active_border` gradyan durakları **ve** açısı ↔
  `gradients.assistant.stops` / `.angle`
- `decoration:shadow:color` ↔ `colors.navy`
- `shell/Theme.qml`'deki `teal`/`purple`/`gold`/`navy` ↔ `colors.*`

Katman 7'den beri **üçü de imajdan** okunuyor (`palette.json`,
`hyprland.conf`, `Theme.qml`) — yani karşılaştırılan şey kullanıcının
gerçekten çalıştıracağı içerik. Kontrolün gerçekten iş gördüğü kasıtlı
sapma enjekte edilerek doğrulandı — gradyan durağı, açı ve `Theme.qml`
sapmalarının üçü de yakalandı.

Gerçek CI sonucu
([run 30664668160](https://github.com/denorath-sys/navigator/actions/runs/30664668160)):

```
OK: ikisi de repodaki dosyalarla birebir aynı (imaj bayat değil).
OK: palette.json <-> hyprland.conf (imajdan) <-> shell/Theme.qml senkron.
    teal=4fd1c5 purple=8b7cf6 gold=e8d9a8 navy=0b0f1a, gradyan açısı=45deg
```

## Duvar kâğıdı

`wallpaper.png` (1672x941) Navigator'ın marka görseli: gece göğü,
takımyıldız, dağ siluetleri ve teal-yeşil bir dalga; sağ kenarda
"Navigator OS" logotipi. `palette.json`'daki nautical/gökyüzü kimliğinin
görsel karşılığı.

İmajda: `image/Containerfile` **Katman 3** dosyayı
`/usr/share/navigator/theme/wallpaper.png` altına koyuyor.
`hyprland/hyprpaper.conf` (Katman 4, `/etc/skel` üzerinden) onu
yüklüyor, `hyprland.conf`'a eklenen `exec-once = hyprpaper` hyprpaper'ı
başlatıyor.

**Neden gerekti:** Navigator bu ana kadar **stok Hyprland duvar
kâğıdını** gösteriyordu ("A day without Hyprland is a day wasted"), yani
masaüstü markasız görünüyordu. Bunu hiçbir metinsel test göremezdi; ilk
gerçek ekran görüntüsü alınınca ortaya çıktı.

### Kısa süre prosedürel bir üretici vardı

Marka görseli gelmeden önce duvar kâğıdı `generate-wallpaper.py` ile
prosedürel olarak üretiliyordu (gece göğü gradyanı + Orion + Kuzey
Yıldızı, renkleri `palette.json`'dan okuyarak, deterministik).
Gerçek marka görseli sağlanınca üretici **kaldırıldı** — iki ayrı
"duvar kâğıdı kaynağı" tutmak yanıltıcı olurdu. Git geçmişinde duruyor
(commit `0a3c4fd`), geri istenirse tek revert.

### Ekranda gerçekten göründüğü nasıl doğrulanıyor

Duvar kâğıdının yüklendiğini iddia etmek yetmez; CI **ekran
görüntüsünü** bu dosyayla karşılaştırıyor
(`.github/scripts/analyze-screenshot.py --reference=theme/wallpaper.png`).
Yöntem: her iki görüntü 24x15 bloğa bölünüp blok ortalama renkleri
karşılaştırılıyor ve farkların **medyanı** alınıyor. Medyan, üst bar ve
asistan paneli gibi ekranı kaplayan pencerelere karşı dayanıklı; onlar
blokların azınlığını bozuyor. hyprpaper'ın "cover" kırpması da hesaba
katılıyor (ekran 16:10, görsel 16:9 → yanlardan %5 kırpılıyor).

Eşik (15) tahmin değil, üç gerçek ölçümden geliyor:

| senaryo | medyan blok farkı |
|---|---|
| aynı duvar kâğıdı (gerçek ekran görüntüsü vs kaynağı) | **0.1** |
| yanlış Navigator duvar kâğıdı | 37.9 |
| stok Hyprland duvar kâğıdı | 68.7 |

**Neden parlaklık değil:** ilk sürüm "masaüstü koyu mu" diye soruyordu
(stok 85.3, üretilmiş duvar kâğıdı 21.6). Gerçek marka görseli gelince o
ölçü çöktü — ortasındaki parlak dalga yüzünden aynı bandın luma'sı 73.0,
yani stok'un 85.3'üne komşu. Parlaklık duvar kâğıdının KİMLİĞİNİ değil
yalnızca bir özetini ölçüyordu; blok karşılaştırması kimliği ölçüyor.

### Bilinen sınırlama: geniş olmayan ekranlarda logotip kırpılıyor

Görsel 16:9 (1672x941, oran 1.777). hyprpaper "cover" ile ölçeklediği
için **16:10 ekranda yanlardan %5 kırpılıyor** ve "Navigator OS"
logotipi x≈%92-97 aralığında olduğundan sağ kısmı kesiliyor (CI'daki
1280x800 VM tam olarak bu durumda). 16:9 ekranlarda sorun yok.
Çözüm istenirse: logotipi biraz sola almak ya da kenarda daha fazla
güvenli alan bırakan bir sürüm.

## Durum

Faz 1 — palet tanımı gerçek ve artık imajda; duvar kâğıdı da gerçek
(marka görseli, imajda, ekran görüntüsüyle doğrulanan). `gtk/`, `qt/` hâlâ
boş iskelet. Gerçek GTK/Qt tema üretimi (ikon seti, cursor teması, GTK
CSS, Qt Kvantum/QQC2 stili) Faz 2 kapsamında ele alınacak.
