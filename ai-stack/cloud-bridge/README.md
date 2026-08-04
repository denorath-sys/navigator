# ai-stack/cloud-bridge/

## Ne yapıyor

`router/` yerel modelin yetersiz olduğuna veya kullanıcının bulut tercih
ettiğine karar verdiğinde devreye giren köprü. **Sağlayıcı: Anthropic Claude
API** (`claude-opus-4-8` varsayılan model). Kimlik bilgisi çözümlemesi
(`ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN` — ortam değişkeninden ya da
`~/.config/navigator/env` dosyasından, bkz. "Kimlik bilgisi nereden
geliyor") ve `/v1/messages` isteği gönderen bir istemci sağlar.

`mcp-tools/` üzerinden gelen araç çağrılarının bulut modeller için de aynı
şekilde çalışmasını sağlamak (Faz 3+) bu modülün sorumluluğunda olacak.

**`router` entegrasyonu (Faz 2):** `route: "cloud"` kararı verildiğinde
`router/cloud.py` bu modülü subprocess ile `--prompt` bayrağıyla çağırır —
bkz. `ai-stack/router/README.md` "Cloud-bridge entegrasyonu".

## Neden resmi SDK değil

Anthropic'in resmi `anthropic` Python SDK'sı (kimlik bilgisi çözümlemesi,
OAuth profilleri, Workload Identity Federation dahil) genel amaçlı Claude
entegrasyonları için önerilen yoldur. Burada bilinçli olarak **stdlib-only
ham HTTP** tercih edildi çünkü:

- Diğer dört ai-stack modülü (`hardware-probe`, `local-runtime`, `router`,
  `mcp-tools`) aynı ilkeyle yazıldı — tutarlılık.
- Navigator OS nihayetinde `image/Containerfile` üzerinden rpm-ostree/dnf ile
  paketlenecek; pip bağımlılıkları bu modele uymuyor (ayrı bir RPM paketleme
  adımı gerektirir).
- Sadece kimlik bilgisi durumu raporlanıyor, gerçek bir API çağrısı henüz
  yapılmıyor — SDK'nın asıl değeri (tool use, streaming, retry mantığı)
  şu an kullanılmıyor.

**Bilinen sınırlama:** Sadece `ANTHROPIC_API_KEY` ve `ANTHROPIC_AUTH_TOKEN`
destekleniyor — resmi SDK'nın yaptığı OAuth profili (`ant auth login`) veya
Workload Identity Federation çözümlemesi YOK.

## Kimlik bilgisi nereden geliyor

İki kaynak var, bu öncelikle (`cloud_bridge/config.py`):

1. **Ortam değişkeni** — `ANTHROPIC_API_KEY`, yoksa `ANTHROPIC_AUTH_TOKEN`.
   Biri tanımlıysa dosya HİÇ açılmaz.
2. **`~/.config/navigator/env`** — kullanıcının kendi dosyası
   (`$XDG_CONFIG_HOME` tanımlı ve mutlaksa oradan).

### Neden bir dosya gerekiyordu

Gerçek imajda `/usr` salt-okunurdur: `cloud-bridge`'in yanına bir
`.env.local` konamaz, kimlik bilgisi imaja da gömülemez (imaj herkese
açık). Geriye "kullanıcı değişkeni kendi oturum ortamına koysun" kalıyordu,
ama asistanı çalıştıran zincir —

```
Hyprland exec-once → Quickshell → Process → python3 -m router → python3 -m cloud_bridge
```

— ortamı compositor'ın başlatıldığı ortamdan miras alıyor. Grafik oturumu
bir greeter'dan ya da TTY login'den açıldığında oraya değişken koymanın
taşınabilir bir yolu yok. Bu yüzden kimlik bilgisi **zincirin ucunda,
ihtiyacı olan modül tarafından** okunuyor: dosya `HOME`'a göreli
çözüldüğünden Quickshell'in ortamı bomboş olsa bile çalışır. Hiçbir
ortam değişkeni plumbing'i, hiçbir shell profili gerekmiyor.

Şablonu imaj kendisi koyuyor: `image/Containerfile` Katman 4
`/etc/skel/.config/navigator/env` altına yorumlanmış, açıklamalı ve **boş**
bir dosya (0600, dizini 0700) yerleştiriyor — yani her yeni hesap dosyayı
yerinde bulur, yolu tahmin etmesi gerekmez, ve imaj güncellemeleri onu
ezmez (`/etc/skel` sadece hesap oluşturma anında okunur).

### İzinler: gevşekse dosya BİLEREK yok sayılır

Dosya sahibi dışında herhangi birine (grup/diğer) açıksa okunmaz —
ssh'ın özel anahtar davranışının aynısı. Sessizce okumak, kullanıcının
API key'inin çok kullanıcılı bir makinede okunabilir olduğunu hiç fark
etmemesi demek olurdu. Bu durumda `reason` ayırt edici olur:

| durum | `reason` |
| --- | --- |
| ne değişken ne dosya var | `credentials_not_configured` |
| dosya var ama izinleri gevşek | `credentials_file_insecure` |
| dosya okunamadı / UTF-8 değil | `credentials_file_unreadable` |
| `KEY=VALUE` olmayan satır var ve hiç anahtar çıkmadı | `credentials_file_malformed` |

`shell/AssistantPanel.qml` bu dizgeleri kullanıcıya Türkçe cümlelere
çeviriyor (`explainReason()`) — "chmod 600 ~/.config/navigator/env"
tavsiyesi dahil.

### Biçim

Her satır `KEY=VALUE`; `#` ile başlayanlar yorum; isteğe bağlı `export `
öneki; değer etrafındaki eşleşen tırnaklar soyulur. Biçim bilinçli olarak
shell'e `source` edilebilir tutuldu, ama burada okuyan bir shell DEĞİL:
**satır-içi yorum yok** (`#` sonrası değerin parçasıdır — bir API key'i
sessizce kesmek teşhisi imkânsız bir 401 üretirdi), `$VAR` genişletmesi
yok, komut ikamesi yok.

Bozuk bir satır ayrıştırmayı durdurmaz: geri kalan satırlardan geçerli bir
anahtar çıkarsa kullanılır, ilk bozuk satırın numarası durum raporunda
`credentials_file_problem: "malformed_line:N"` olarak görünür.

Kimlik bilgisinin **kendisi** hiçbir zaman raporlanmaz/log'lanmaz; durum
raporu sadece kaynağı (`credentials_source`), yolu (`credentials_file`) ve
varsa problemi taşır.

## Kullanım

Harici bağımlılık yok, sadece Python 3.11+ (stdlib).

```sh
cd ai-stack/cloud-bridge
python3 -m cloud_bridge --pretty                     # sadece kimlik bilgisi durumu
python3 -m cloud_bridge --prompt "merhaba" --pretty   # gerçek istek (kimlik bilgisi varsa)
```

**`--converse`** (Faz 4'te `ai-stack/assistant` için eklendi): stdin'den
tam bir mesaj listesi + isteğe bağlı `tools` şeması okur, Claude API'nin
HAM yanıtını (`tool_use` blokları, `stop_reason` dahil — `--prompt`'un
basitleştirilmiş raporunun aksine) stdout'a basar. Çok turlu tool-use
döngüsü kuran çağıranlar için (`--prompt` tek turlu ve tool'suz kalmaya
devam ediyor):

```sh
echo '{"messages": [{"role": "user", "content": "merhaba"}], "tools": [...]}' \
  | python3 -m cloud_bridge --converse
```

Testler:

```sh
cd ai-stack/cloud-bridge
python3 -m unittest discover -v -s tests
```

### Kimlik bilgisini yerel olarak bağlamak (`.env.local`)

Bu makinede gerçek bir Anthropic API key `.env.local` dosyasına yazıldı
(`.gitignore`'da `.env*` deseni ile hariç tutuluyor — asla commit
edilmez, sadece bu geliştirme makinesinde var). Kullanmak için her
zaman elle source edilmesi gerekiyor (Bash tool çağrıları arasında
shell state kalıcı değil):

```sh
cd ai-stack/cloud-bridge
set -a && source .env.local && set +a
python3 -m cloud_bridge --prompt "merhaba" --pretty
```

`.env.local` bir GELİŞTİRME kolaylığı olarak kaldı; gerçek makinedeki yol
`~/.config/navigator/env` (yukarı bkz.). Aralarındaki fark ortam
değişkeni önceliğinden geliyor: `source` edilen `.env.local` ortama
yazdığı için dosyanın önüne geçer.

Kimlik bilgisine bağlı testler (`test_prompt_cli.py`,
`router/tests/test_integration.py`) kimlik bilgisi hiç yoksa otomatik
`skip` olur (CI'da da böyle davranır — GitHub Actions'ta secret yok).
Bu testlerin "kimlik bilgisi var mı" kapısı artık ortam değişkenine
elle bakmıyor, üretimin kullandığı çözümlemenin AYNISINI çağırıyor
(`resolve_credentials()`); router tarafı bunu `python3 -m cloud_bridge`
subprocess'ine sorarak yapıyor, böylece kural iki yerde ayrışamaz.

Tersine, "kimlik bilgisi YOK" iddia eden testler artık `HOME`'u da boş
bir dizine çekiyor — yoksa geliştiricinin kendi
`~/.config/navigator/env`'i o testleri sessizce anlamsızlaştırırdı.

## Çıktı örneği

Kimlik bilgisi ayarlı değilken:

```json
{
  "schema_version": "0.1",
  "provider": "anthropic",
  "default_model": "claude-opus-4-8",
  "credentials_configured": false,
  "credentials_source": null,
  "credentials_file": "/var/home/navtest/.config/navigator/env",
  "credentials_file_problem": null
}
```

`credentials_file` dosya yokken bile yazılıyor: kullanıcının hangi yolu
oluşturması gerektiğini `--pretty` çıktısından görebilmesi için.
Kimlik bilgisi dosyadan çözüldüğünde `credentials_source: "file"`,
ortamdan geldiğinde `"environment"` olur.

`--prompt` verildiğinde (kimlik bilgisi yokken):

```json
{
  "schema_version": "0.1",
  "provider": "anthropic",
  "model": "claude-opus-4-8",
  "prompt_preview": "merhaba",
  "status": "unavailable",
  "reason": "credentials_not_configured"
}
```

`.env.local` source edilip kimlik bilgisi varken (bu makinede gerçek bir
API çağrısıyla doğrulandı):

```json
{
  "schema_version": "0.1",
  "provider": "anthropic",
  "model": "claude-opus-4-8",
  "prompt_preview": "Tek kelimeyle cevap ver: Türkiye'nin başkenti neresi?",
  "status": "ok",
  "content": "Ankara"
}
```

## `is_available()` neden ağ çağrısı yapmıyor

`local-runtime`'ın `OllamaClient.is_available()`'ı `localhost:11434/api/version`'a
gerçek bir çağrı yapar (ücretsiz, yerel). Anthropic API'sinde ücretsiz bir
"ping" uç noktası yok — bu yüzden `AnthropicClient.is_available()` sadece
kimlik bilgisinin çözülüp çözülmediğine bakıyor, gerçek bir istek
göndermiyor.

Çözümleme her çağrıda yeniden yapılır, önbelleklenmez: kullanıcı dosyayı
oluşturduktan ya da `chmod 600` ile düzelttikten sonra asistanı yeniden
başlatmak zorunda kalmasın diye. Maliyeti çağrı başına birkaç yüz baytlık
bir dosya okuması (dosya yoksa tek bir `stat`).

## Kapsam dışı — henüz yapılmadı

- Gizlilik filtrelemesi (isteğe gönderilmeden önce hassas veri maskeleme) yok.
- Streaming yok — her yanıt tek seferde, tam olarak döner.
- CI'da kimlik bilgisi YOK ve bilinçli olarak olmayacak: ne `.env.local`
  ne de gerçek bir `~/.config/navigator/env` commit ediliyor, GitHub
  Actions'ta secret olarak da tanımlı değil. Dolayısıyla CI'da bulut yolu
  hep "unavailable" raporlar. Buna rağmen kimlik bilgisi YOLU CI'da
  gerçekten test ediliyor: boot testinde imajın içinde SAHTE bir anahtarla
  bir `~/.config/navigator/env` kurulup çözümlemenin gerçekten çalıştığı,
  izinler gevşetilince gerçekten reddedildiği doğrulanıyor — API'ye hiç
  çıkmadan.
- Dosyadaki kimlik bilgisi düz metin. Çekirdek keyring/gnome-keyring
  entegrasyonu YOK; bu bilinçli bir ilk adım (stdlib-only, servis
  bağımlılığı yok) ama gerçek bir sınırlama.

## Durum

Faz 2 — kimlik bilgisi/istemci katmanı, `router` entegrasyonu VE gerçek
bir Claude API kimlik bilgisi bağlantısı tamamlandı (`client.py`,
`status.py`, `python3 -m cloud_bridge [--prompt ...]` CLI). Faz 4'te
çok turlu mesaj + tool-use desteği eklendi (`send_messages()`,
`--converse`) — `ai-stack/assistant`'ın gerçek bir tool-use döngüsü
kurabilmesi için. Gerçek bir API key `.env.local`'a yazıldı (gitignore'lı)
ve gerçek isteklerle uçtan uca doğrulandı — hem doğrudan `cloud_bridge`
CLI'ı hem `router → cloud_bridge` zinciri hem de `assistant`'ın gerçek
tool-use döngüsü üzerinden (mcp-tools'un `hardware_tier` aracını gerçekten
çağırıp doğru donanım verisiyle cevap üretti).

**Kullanıcı seviyesinde kimlik bilgisi yolu eklendi** (`config.py`):
gerçek bir masaüstünde asistanın kullanılabilir olmasını engelleyen son
parça buydu — `/usr` salt-okunur, Quickshell'in ortamına değişken koymanın
taşınabilir yolu yok. Artık `~/.config/navigator/env` okunuyor, şablonu
imaj `/etc/skel` üzerinden koyuyor. Gerçek bir API key'le uçtan uca
doğrulandı: ortamda hiçbir `ANTHROPIC_*` değişkeni yokken hem doğrudan
`cloud_bridge --prompt` hem de `router → cloud_bridge` zinciri sadece
dosyadan çözülen kimlik bilgisiyle gerçek bir Claude yanıtı üretti
("Ankara"). İzin reddi de gerçek bir denemeyle doğrulandı: aynı dosya
`chmod 644` yapıldığında `reason: credentials_file_insecure`.

50 test geçiyor (mock'lanmış HTTP + gerçek CLI entegrasyon testleri +
kimlik bilgisi çözümlemesinin geçici bir `HOME` altında gerçek dosya ve
gerçek izinlerle test edildiği `test_config.py`; kimlik bilgisiz yol her
zaman çalışır, kimlik bilgili gerçek-API testleri kimlik bilgisi
bulunamadığında otomatik `skip` olur).
