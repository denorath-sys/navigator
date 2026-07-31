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

## Durum

Faz 1 — palet tanımı gerçek ve artık imajda; `gtk/`, `qt/` hâlâ boş
iskelet. Gerçek GTK/Qt tema üretimi (ikon seti, cursor teması, GTK CSS,
Qt Kvantum/QQC2 stili) Faz 2 kapsamında ele alınacak.
