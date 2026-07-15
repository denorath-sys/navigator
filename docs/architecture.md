# Navigator OS — Mimari Özet

Bu doküman, Faz 1 başlangıç yönergesinde tanımlanan nihai mimarinin özetidir.
Aşağıdaki bileşenlerin çoğu **ileride kurulacak**; bu doküman şu anki niyeti
kayıt altına almak içindir, mevcut implementasyon durumu için ilgili
klasörlerin README'lerine bakın.

## Katmanlar

### Taban işletim sistemi

**Fedora Atomic**, OSTree tabanlı, aylık güncellenen immutable bir imaj
olarak kurulacak. Kullanıcı sistemi doğrudan değiştirmez; değişiklikler
katmanlı imaj güncellemeleri (`rpm-ostree` / `bootc`) üzerinden gelir.
Referans base image: [`ghcr.io/ublue-os/base-main`](https://github.com/ublue-os/main)
(Universal Blue'nun DE içermeyen minimal tabanı — Hyprland üzerine bizim
katmanladığımız bir katman). Tanım dosyası: [`image/Containerfile`](../image/Containerfile).

### Masaüstü ortamı

**Hyprland**, dinamik tiling özellikli bir Wayland compositor'ü olarak
seçildi — performans ve özelleştirilebilirlik önceliği. Üzerine
**Quickshell** (Qt6/QML) tabanlı özgün bir shell inşa edilecek (panel,
bildirimler, asistan paneli, launcher) — AGS/Astal'a karşı QML'in
performans avantajı ve daha az hazır şablona bağımlı, özgün bir kimlik
kurma tercihiyle seçildi. Bkz. [`hyprland/`](../hyprland/) ve
[`shell/`](../shell/).

### AI Stack

Beş bileşenden oluşan hibrit yerel/bulut mimari:

1. **hardware-probe** — donanım tespiti, model tier kararı
2. **local-runtime** — llama.cpp/Ollama ile yerel model çalıştırma
3. **mcp-tools** — MCP (Model Context Protocol) tabanlı araç erişimi
4. **router** — istekleri yerel/bulut arasında yönlendiren karar katmanı
5. **cloud-bridge** — bulut model sağlayıcılarına bağlantı

Detaylar: [`ai-stack/README.md`](../ai-stack/README.md).

### Marka kimliği

Pusula, deniz feneri, Orion takımyıldızı ve Kuzey Yıldızı temalı
nautical/gökyüzü kimliği. Renk paleti: teal `#4fd1c5`, mor `#8b7cf6`,
altın `#e8d9a8`, lacivert taban `#0b0f1a`. Bkz.
[`theme/palette.json`](../theme/palette.json).

## Tasarım ilkeleri

Navigator'daki her özellik, eklenmeden önce şu soruları geçmeli. Her ilkenin
yanında, Faz 1-3'teki gerçek ilerlemeye göre güncel durumu belirtilmiştir.

- **Bu özellik kullanıcının hayatını gerçekten kolaylaştırıyor mu?**
  Cevap "hayır" ise, teknik olarak ne kadar etkileyici olursa olsun
  Navigator'a ait değildir.
  *Durum:* Henüz test edilemiyor — kullanıcıya görünen bir yüz (asistan
  paneli) yok. Faz 4'te gerçek sınav başlayacak.

- **Sıfır manuel yapılandırma.**
  Kullanıcı Bluetooth kulaklık, ikinci monitör, dock, RGB, touchpad gibi
  şeyleri elle ayarlamak zorunda kalmamalı — sistem donanımı tanıyıp kendi
  hazırlamalı.
  *Durum:* Gerçekleşti — `ai-stack/hardware-probe`, kullanıcıdan girdi
  almadan donanım tier'ını kendi tespit ediyor.

- **Çıkmaz sokak yok (No Dead Ends).**
  Bir hata oluştuğunda ekranda çıplak bir hata kodu değil, "şu sorun
  oluştu, şöyle çözebiliriz, birlikte yapalım mı?" akışı olmalı.
  *Durum:* Henüz test edilmedi (UI'a bağlı). Faz 4'te asistan paneli
  tasarlanırken sona eklenecek bir özellik değil, en baştan mimariye
  girmesi gereken bir gereksinim olarak ele alınmalı.

- **Her şey keşfedilebilir olmalı.**
  Kullanıcı "linux'ta çift monitör nasıl kurulur" diye web'de aramak
  yerine, doğrudan Navigator Asistan'a sorabilmeli ve orada çözüm
  bulmalı.
  *Durum:* Temeli atıldı — `list_windows`, `active_window`,
  `list_workspaces` gibi Hyprland sorgu araçları hazır. Gerçek kanıt,
  asistan panelinde bir soru sorulup doğru cevap alındığında oluşacak.

- **AI, gerekmediği yerde kullanılmaz.**
  Bir özellik AI olmadan da aynı kalitede çözülebiliyorsa, AI kullanılmaz.
  *Durum:* Kısmen gerçekleşti — dosya sistemi araçları (`read_file`,
  `write_file` vb.) doğrudan araç çağrıları, AI karar vermiyor;
  `router`'ın yerel/bulut seçimi de gereksiz yere pahalı model kullanmama
  mantığıyla örtüşüyor.

- **Linux altyapıdır, Navigator deneyimdir.**
  Fedora Atomic taban, teknik bir seçim olarak kalır; kullanıcının
  gördüğü ve hissettiği şey Navigator'ın kendi kimliğidir.
  *Durum:* Net şekilde gerçekleşti — taban Fedora Atomic, kullanıcı yüzü
  Hyprland + Quickshell + AI stack olarak ayrışmış durumda.

- **Gerçek olmayan hiçbir şey "başarılı" gösterilmez.**
  Sistem, yapamadığı bir şeyi yapabiliyormuş gibi göstermez — "bunu
  deneyemedim çünkü X" der. Bu, "çıkmaz sokak yok" ilkesinin dürüstlük
  boyutudur.
  *Durum:* Gerçekleşti — Faz 1-3 boyunca mock yerine gerçek test tercih
  edildi (gerçek Ollama, gerçek Claude API, gerçek KVM boot), ertelenen
  Hyprland/Quickshell compositor testi açıkça "bilinen sınırlama" olarak
  belgelendi, başarılı gibi gösterilmedi.

- **Sistemi değiştiren her eylem, açık onay ister.**
  Yapılandırma otomatik olur (bkz. ilke 2), ama tahribat riski olan
  eylemler otomatik olmaz — AI, kullanıcının rızası varsayılmadan
  sistemi değiştirmez.
  *Durum:* Gerçekleşti — MCP dosya araçlarında path traversal koruması
  ve overwrite/confirm mekanizması, 200MB+ indirmelerde proje sahibi
  onayı, riskli CI tetiklemelerinin varsayılmaması.

Bu ilkeler, Faz 1-5 boyunca her teknik/tasarım kararında referans noktası
olarak kullanılır. Yeni bir özellik önerisi bu listeyle çelişiyorsa, önce
burada tartışılmalı. Durum notları her faz sonunda gözden geçirilip
güncellenmelidir.

## Faz durumu

Güncel yol haritası için kök [`README.md`](../README.md#yol-haritası)
dosyasına bakın.
