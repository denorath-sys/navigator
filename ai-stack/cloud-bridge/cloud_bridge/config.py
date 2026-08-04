"""Kullanıcı seviyesinde kimlik bilgisi yapılandırması — `~/.config/navigator/env`.

Neden var: Navigator imajında `/usr` salt-okunurdur, yani
`/usr/share/navigator/ai-stack/cloud-bridge/.env.local` gibi bir dosya
oluşturulamaz; kimlik bilgisi imaja da gömülmez. Geriye tek yol olarak
"kullanıcı değişkeni kendi oturum ortamına koysun" kalıyordu, ama asistanı
başlatan zincir (Hyprland `exec-once` → Quickshell → `Process` →
`python3 -m router` → `python3 -m cloud_bridge`) ortamı compositor'ın
başlatıldığı ortamdan miras alıyor: grafik oturumu bir greeter'dan veya
TTY login'den açıldığında oraya değişken koymanın taşınabilir bir yolu yok.

Bu yüzden kimlik bilgisi ZİNCİRİN UCUNDA, ihtiyacı olan modül tarafından
dosyadan okunuyor. Ortam değişkeni plumbing'i gerektirmez: dosya HOME'a
göreli çözüldüğü için Quickshell'in ortamı boş olsa bile çalışır.

Dosya biçimi bilinçli olarak shell ile `source` edilebilir tutuldu
(`KEY=VALUE`, `#` yorum, isteğe bağlı `export ` öneki) — böylece aynı dosya
hem buradan okunabilir hem de bir terminalde `set -a && source ~/.config/
navigator/env && set +a` ile kullanılabilir. Ama burada okunan bir SHELL
DEĞİL: `$VAR` genişletmesi, komut ikamesi ve satır-içi yorum YOKTUR; değer,
`=`'den satır sonuna kadar olan (kırpılmış, gerekirse tırnakları soyulmuş)
metnin tamamıdır.
"""
import os
import re
from pathlib import Path
from typing import NamedTuple

# Dosya adı "env" — bir gün kimlik bilgisi dışında Navigator ayarları da
# gerekirse onlar ayrı bir dosyaya (ör. config.toml) girmeli; burası
# "shell'e source edilebilir ortam değişkenleri" sözleşmesini korusun.
CONFIG_RELATIVE_PATH = Path("navigator") / "env"

# Bugün SADECE bu iki anahtar okunuyor. Dosyadaki diğer satırlar
# ayrıştırılır ama yok sayılır — bu dosya bir ortam dosyası taklidi değil,
# cloud-bridge'in kimlik bilgisi kaynağı.
CREDENTIAL_KEYS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")

# Dosya bir sırrı barındırıyor: grup/diğer için herhangi bir bit açıksa
# okumayı REDDEDİYORUZ (ssh'ın özel anahtar davranışı). Sessizce okumak,
# kullanıcının API key'inin çok kullanıcılı bir makinede okunabilir
# olduğunu fark etmemesi demek olurdu.
INSECURE_MODE_MASK = 0o077

_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

PROBLEM_INSECURE = "insecure_permissions"
PROBLEM_UNREADABLE = "unreadable"
PROBLEM_MALFORMED = "malformed_line"

# Kimlik bilgisi bulunamadığında CLI/durum raporunun döndürdüğü sebep.
# Panel bu dizgeyi kullanıcıya gösterdiği için "neden olmadı" ayırt
# edilebilir olmalı: yapılandırılmamış olmakla, yanlış izinler yüzünden
# REDDEDİLMİŞ olmak aynı şey değil.
_PROBLEM_REASONS = {
    PROBLEM_INSECURE: "credentials_file_insecure",
    PROBLEM_UNREADABLE: "credentials_file_unreadable",
    PROBLEM_MALFORMED: "credentials_file_malformed",
}
REASON_NOT_CONFIGURED = "credentials_not_configured"

SOURCE_ENVIRONMENT = "environment"
SOURCE_FILE = "file"


class CredentialResolution(NamedTuple):
    """Kimlik bilgisinin nereden geldiği (veya neden gelmediği).

    `values` sadece CREDENTIAL_KEYS'ten gerçekten bulunanları içerir;
    hiçbir zaman log'lanmaz/raporlanmaz — çağıranlar `source`, `path` ve
    `problem`'i raporlar, değerleri değil.
    """

    values: dict
    source: str | None
    path: Path
    problem: str | None

    @property
    def unavailable_reason(self) -> str:
        """Kimlik bilgisi yokken raporlanacak makine-okunur sebep."""
        if self.problem:
            base = self.problem.split(":", 1)[0]
            return _PROBLEM_REASONS.get(base, REASON_NOT_CONFIGURED)
        return REASON_NOT_CONFIGURED


def config_path(environ: dict | None = None) -> Path:
    """`$XDG_CONFIG_HOME/navigator/env`, yoksa `~/.config/navigator/env`.

    XDG Base Directory spec'i: XDG_CONFIG_HOME tanımsız, boş VEYA mutlak
    değilse yok sayılıp varsayılan kullanılır.
    """
    environ = os.environ if environ is None else environ
    xdg = environ.get("XDG_CONFIG_HOME", "")
    base = Path(xdg) if xdg.startswith("/") else Path(environ.get("HOME", "~")).expanduser() / ".config"
    return base / CONFIG_RELATIVE_PATH


def parse_env_text(text: str) -> tuple[dict, str | None]:
    """`KEY=VALUE` satırlarını ayrıştırır → (değerler, problem).

    Bozuk bir satır ayrıştırmayı DURDURMAZ (kullanıcı geri kalanı doğru
    yazmış olabilir) ama ilk bozuk satırın numarası problem olarak
    döndürülür ki durum raporunda görünsün.
    """
    values: dict = {}
    problem: str | None = None

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export ") or line.startswith("export\t"):
            line = line[len("export ") :].strip()

        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not _KEY_RE.match(key):
            if problem is None:
                problem = f"{PROBLEM_MALFORMED}:{lineno}"
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value

    return values, problem


def resolve_credentials(
    environ: dict | None = None, path: Path | None = None
) -> CredentialResolution:
    """Kimlik bilgisini ortamdan, yoksa yapılandırma dosyasından çözer.

    Öncelik ORTAM: CREDENTIAL_KEYS'ten herhangi biri ortamda tanımlıysa
    dosya hiç açılmaz. Böylece `set -a && source .env.local` ile çalışan
    geliştirme akışı, CI ve tek seferlik `ANTHROPIC_API_KEY=... komut`
    kullanımları dosyadan bağımsız kalır; ayrıca ortamı bilerek ayarlamış
    bir kullanıcı, dosyanın izin uyarısıyla karşılaşmaz.
    """
    environ = os.environ if environ is None else environ
    path = config_path(environ) if path is None else path

    from_env = {k: environ[k] for k in CREDENTIAL_KEYS if environ.get(k)}
    if from_env:
        return CredentialResolution(from_env, SOURCE_ENVIRONMENT, path, None)

    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        return CredentialResolution({}, None, path, None)
    except OSError:
        return CredentialResolution({}, None, path, PROBLEM_UNREADABLE)

    if mode & INSECURE_MODE_MASK:
        return CredentialResolution({}, None, path, PROBLEM_INSECURE)

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return CredentialResolution({}, None, path, PROBLEM_UNREADABLE)

    parsed, problem = parse_env_text(text)
    values = {k: parsed[k] for k in CREDENTIAL_KEYS if parsed.get(k)}
    return CredentialResolution(values, SOURCE_FILE if values else None, path, problem)
