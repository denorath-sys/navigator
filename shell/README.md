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

## İmajdaki kurulum yolu (Katman 7)

Katman 2 Quickshell'in kendisini (çalıştırıcı) kuruyor; **Katman 7** bu
dizindeki `.qml` dosyalarını imaja koyuyor:

```
/usr/share/navigator/shell/*.qml
```

Çalıştırma: `qs -p /usr/share/navigator/shell/shell.qml`

**Neden `/usr/share/navigator/` ve `/etc/skel` değil:** bunlar kullanıcı
yapılandırması değil program kodu. `/etc/skel`'e konsaydı her kullanıcı
kendi donmuş kopyasını alır, imaj güncellemeleri shell'i hiç
güncelleyemezdi. `hyprland.conf`'ta (Katman 4) istediğimiz bunun tam
tersiydi — orada kullanıcının dosyasını *ezmemek* doğruydu; burada
*güncelleyebilmek* doğru. Kendi shell'ini çalıştırmak isteyen kullanıcı bu
dizini kopyalayıp `qs -p` ile kendi yolunu gösterebilir.

`README.md` imaja girmiyor (geliştirici belgesi). Katman sırası
bağımlılık değil, katmanların gerçek olma sırasını izliyor; shell/ en sık
değişen COPY içeriği olduğu için sonda olması üstündeki katmanların build
cache'ini de koruyor.

Bu katmandan sonra `build-disk-and-boot-test.yml`'de runner'dan VM'e
kopyalanan **tek şey test betiğinin kendisi** — test edilen her Navigator
bileşeni imajdan geliyor.

## Dosyalar

- `shell.qml` — Quickshell giriş noktası (`ShellRoot`); `assistantVisible`
  durumunu ve iki `IpcHandler`'ı tutar:
  - `target: "assistant"` — `toggle()`/`ask(prompt)`/`getResponse()`/
    `isLoading()`; hem `Bar.qml`'deki tıklamayı hem Hyprland Super+Space
    kısayolunu (`qs ipc call assistant toggle`) `AssistantPanel`'e bağlar.
  - `target: "workspaces"` — `list()`/`focusedId()`; `WorkspaceIndicator`'ın
    bağlandığı canlı Hyprland verisini dışarıdan okunabilir yapar
    (aşağıya bkz.).
- `Theme.qml` — Navigator marka paleti (`../theme/palette.json` ile manuel
  senkron tutulur, `hyprland/hyprland.conf`'un renk senkron yöntemiyle
  aynı). Bu manuel senkron artık CI'da **gerçekten doğrulanıyor**: dört
  renk sabiti imajdaki `palette.json` ile karşılaştırılıyor (bkz.
  `theme/README.md`).
- `Bar.qml` — üst panel (`PanelWindow`, wlr-layer-shell)
- `WorkspaceIndicator.qml` — workspace göstergesi, **gerçek Hyprland
  IPC'sine bağlı** (`Quickshell.Hyprland`); tıklanabilir (bkz.
  "WorkspaceIndicator — gerçek Hyprland verisi")
- `AssistantToggle.qml` — AI asistan paneli anahtarı; tıklanınca `toggled()`
  sinyali yayar (`Bar.qml` üzerinden `shell.qml`'e bağlı)
- `AssistantPanel.qml` — **`ai-stack/router`'a gerçekten bağlı** asistan
  paneli: metin girişi + `ai-stack/router`'ı `Quickshell.Io.Process` ile
  subprocess olarak çağıran mantık + gerçek yanıtı (route + içerik, ya da
  graceful hata) gösteren alan (bkz. "AssistantPanel — gerçek router
  entegrasyonu" aşağıda)
- `Clock.qml` — canlı saat göstergesi

## Gerçek compositor'da runtime doğrulaması (CI, Faz 4)

Quickshell, Fedora'ya özel bir COPR paketi (Qt 6.10 gerektiriyor) olduğundan
bu geliştirme ortamında (Debian tabanlı, Qt 6.8.2) hâlâ kurulamıyor —
ama artık CI'da gerçek bir compositor'a karşı doğrulanıyor.

`.github/workflows/build-disk-and-boot-test.yml`'deki `hyprland-test`
job'ı, Hyprland gerçekten başladıktan sonra shell'i **imajdaki
yolundan** — `qs -p /usr/share/navigator/shell/shell.qml` — gerçekten
başlatıyor (Katman 7 öncesinde bu dizin runner'dan VM'e kopyalanıyordu;
o son taklit de kalktı). (Hyprland'ın
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
piksel piksel doğru olduğu test edilmedi (headless VNC display'den ekran
görüntüsü almak ek karmaşıklık gerektirir). `WorkspaceIndicator`'ın
VERİSİ artık doğrulanıyor (aşağıya bkz.) ama pil'e yapılan gerçek bir
FARE TIKLAMASI hâlâ test edilmiyor: `activate()` çağrısı kod
incelemesiyle doğru, tıklama yolunun kendisi ekran görüntüsü/girdi
enjeksiyonu gerektiriyor.

## WorkspaceIndicator — gerçek Hyprland verisi (CI, Faz 4)

`WorkspaceIndicator` uzun süre statik bir placeholder'dı: 1-10 arası
sabit, tıklanamayan piller. Artık `Quickshell.Hyprland`'ın `Hyprland`
singleton'ına bağlı — `Hyprland.workspaces` (`ObjectModel`) doğrudan
`Repeater`'ın modeli, `focused`/`active` durumları renkleri sürüyor ve
tıklama `HyprlandWorkspace.activate()` çağırıyor.

**Polling yok.** Quickshell compositor'ın event soketini (`socket2`)
kendisi dinliyor, yani workspace açılıp kapandığında veya odak
değiştiğinde model kendiliğinden güncelleniyor.

**Görünür davranış değişikliği:** artık sadece VAR OLAN workspace'ler
gösteriliyor — Hyprland boş workspace'leri raporlamaz, dolayısıyla liste
kullanımla birlikte büyüyüp küçülüyor. Sabit 1-10 pil görüntüsü
kayboldu; `hyprland.conf`'taki Super+[1-9,0] kısayolları o
workspace'leri oluşturmaya devam ediyor ve gösterge onları
oluştuklarında gösteriyor. Negatif id'li özel workspace'ler
(scratchpad vb.) numaralı listede gizleniyor.

### Nasıl doğrulanıyor

Gösterge grafiksel olduğundan "doğru veriyi gösteriyor" iddiasının tek
kanıtı, bağlandığı veriyi dışarıdan okumak: `shell.qml`'e
`IpcHandler { target: "workspaces" }` eklendi (`assistant`
handler'ındaki `getResponse`/`isLoading` ile aynı kalıp). CI iki ayrı
şeyi doğruluyor:

1. **Uyum** — shell'in gördüğü workspace kümesi ve odak, compositor'ın
   kendi raporuyla (`hyprctl workspaces -j`, `hyprctl activeworkspace -j`)
   birebir aynı mı.
2. **Canlılık** — `hyprctl dispatch workspace 3` ile compositor'da
   gerçek bir değişiklik yapılıyor ve shell'in bunu KENDİLİĞİNDEN
   görmesi bekleniyor (sabit uyku değil, `focusedId` 3 olana kadar
   döngü). Statik bir placeholder ya da tek seferlik bir okuma bu
   ikinciyi geçemez.

Karşılaştırma mantığı, CI harcanmadan yerelde sahte verilerle sınandı;
kasıtlı üç sapma (shell bir workspace'i kaçırıyor, odak yanlış, eski
sabit 1-10 davranışı) üçü de yakalandı.

## AssistantPanel — gerçek `ai-stack/router` entegrasyonu (CI, Faz 4)

`AssistantToggle` artık sadece bir konsol logu yazmıyor — `AssistantPanel`'i
açıp kapatıyor, ve bu panel `ai-stack/router`'ı **gerçekten** çağırıyor
(`Quickshell.Io.Process` ile `python3 -m router --prompt <soru>`,
`/usr/share/navigator/ai-stack/router` içinde). `shell.qml`'deki
`IpcHandler` (`target: "assistant"`) hem `Bar.qml`'deki tıklamayı hem
Hyprland Super+Space kısayolunu (`hyprland/hyprland.conf`: artık
`exec, qs ipc call assistant toggle`, eskiden placeholder `echo`) aynı
panele bağlıyor.

`router`'ın kurulum yolu artık bir varsayım değil: `image/Containerfile`
**Katman 5** ai-stack'in altı modülünü `/usr/share/navigator/ai-stack/`
altına gerçekten kopyalıyor (bkz. `ai-stack/README.md`, "İmajdaki kurulum
yolu"). İlk sürümde bu yol CI'da scp + `rpm-ostree usroverlay` ile taklit
ediliyordu; o taklit kaldırıldı, `hyprland-test` job'ı artık `/usr`
salt-okunur haldeyken imajın kendi içeriğini doğruluyor. Sonra
`qs ipc -p /usr/share/navigator/shell/shell.qml call assistant ask
"<soru>"` ile gerçek bir soru soruluyor ve `getResponse()`/`isLoading()` ile sonuç okunuyor.

Gerçek sonuç (CI'da ne Ollama ne Claude API kimlik bilgisi var, bu
yüzden `model_ready=false` kuralıyla her zaman "cloud"a düşüyor ve
`cloud-bridge` kimlik bilgisiz olduğundan graceful "unavailable"
dönüyor — mock değil, gerçek bir uçtan uca hata yolu):

```
AssistantPanel yanıtı: [cloud] unavailable: credentials_not_configured
```

**Sebep dizgeleri artık kullanıcıya çevriliyor** (`explainReason()`):
`credentials_not_configured` gibi makine-okunur bir slug bir masaüstü
kullanıcısına hiçbir şey anlatmıyordu. Panel artık bilinen sebepler için
ne yapılacağını söylüyor — ör. "Claude kimlik bilgisi yok —
`~/.config/navigator/env` dosyasına `ANTHROPIC_API_KEY=...` yazıp dosyayı
`chmod 600` yapın", ya da izinler gevşekse "başkaları tarafından
okunabilir, bu yüzden yok sayıldı". Bilinmeyen sebepler OLDUĞU GİBİ
gösteriliyor: eşleşmeyen bir sebebi "bilinmeyen hata"ya yuvarlamak,
teşhis için gereken tek bilgiyi silmek olurdu. Kimlik bilgisi yolunun
kendisi için bkz. `ai-stack/cloud-bridge/README.md`.

**Yol boyunca bulunup düzeltilen gerçek sorunlar:**
- `qs ipc call`, `-p`/`--path`'i `ipc` alt komutunun kendisine kayıtlı
  bekliyor (`call`'a değil) — kaynağında (`launch/parsecommand.cpp`)
  doğrulandı; doğru sözdizimi `qs ipc -p <yol> call <target> <fn>`.
- `ai-stack/router`'ın kendisi VM'e kopyalandıktan sonra bile
  başarısız oluyordu: `local-runtime`'ın kendi varsayılan
  `--hardware-probe-path` (`../hardware-probe`) bağımlılığı hiç
  kopyalanmamıştı — Quickshell'den bağımsız, doğrudan SSH ile
  izole edilip bulundu (bkz. CI'daki "ai-stack/router'ı doğrudan
  SSH ile test et" adımı, kalıcı bir regresyon kontrolü olarak
  bırakıldı).

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

## Çalıştırma

İmaj içinde (Katman 7'den beri gerçek yol):

```sh
qs -p /usr/share/navigator/shell/shell.qml
```

Repodan, geliştirirken:

```sh
cd shell
qs -p shell.qml
```

Elle çalıştırmak genelde gerekmiyor: `hyprland/hyprland.conf`'taki
`exec-once` shell'i oturum açılışında başlatıyor (bkz.
`hyprland/README.md` "Otomatik başlatma"). CI de artık elle
başlatmıyor — Hyprland'ın `exec-once`'ının gerçekten çalıştığını
doğruluyor.

## Statik analiz (şimdi, herhangi bir Qt6 ortamında)

```sh
cd shell
for f in *.qml; do qt6-qmllint "$f" || /usr/lib/qt6/bin/qmllint "$f"; done
```

(Paket adı dağıtıma göre değişir — Debian/Pardus'ta `qt6-declarative-dev-tools`,
Fedora'da `qt6-qtdeclarative-devel` benzeri.)

## Kapsam (ileride)

- ~~Üst panel: workspace göstergesi, saat~~ — gerçek (workspace göstergesi
  artık canlı Hyprland verisine bağlı)
- ~~AI asistan paneli — gerçek implementasyon~~ — `ai-stack/router`'a
  gerçekten bağlı, CI'da doğrulandı (bkz. "AssistantPanel — gerçek
  ai-stack/router entegrasyonu")
- ~~`ai-stack`'in `image/Containerfile`'a gerçek bir katman olarak
  eklenmesi~~ — Katman 5 artık gerçek, CI `/usr` salt-okunur haldeyken
  doğruluyor
- ~~`shell/`in imaja katmanlanması~~ — Katman 7 artık gerçek
- ~~Hyprland'ın shell'i otomatik başlatması (`exec-once`)~~ — eklendi,
  CI otomatik başlatmayı gerçekten doğruluyor
- Alt panel / bildirim merkezi
- Uygulama başlatıcı (wofi'nin yerini alacak özgün launcher)
- ~~Gerçek Hyprland IPC entegrasyonu (aktif/dolu workspace tespiti)~~ —
  `WorkspaceIndicator` artık `Quickshell.Hyprland`'a bağlı, CI gerçek bir
  compositor'da doğruluyor

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
**`AssistantToggle` artık `ai-stack/router`'a gerçekten bağlı**
(`AssistantPanel.qml`, yeni) — aynı CI'da uçtan uca doğrulandı (bkz.
"AssistantPanel — gerçek ai-stack/router entegrasyonu"), ve panelin
çağırdığı `/usr/share/navigator/ai-stack/router` yolu artık imajın
kendisinden geliyor (Containerfile Katman 5). Kalan: görsel piksel
doğruluğu, gerçek Hyprland IPC (workspace/pencere verisi),
tıklama/etkileşim testleri.
