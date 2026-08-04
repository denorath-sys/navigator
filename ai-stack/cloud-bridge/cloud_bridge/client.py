"""Anthropic Claude API için ince istemci — stdlib-only (harici bağımlılık yok).

Not: Resmi `anthropic` Python SDK'sı kimlik bilgisi çözümlemesini (API key →
auth token → OAuth profili → Workload Identity Federation → disk profili)
otomatik yapar ve önerilen yoldur. Burada diğer ai-stack modülleriyle aynı
stdlib-only ilkesi korunmak istendiği için (Navigator OS'un rpm-ostree/
Containerfile paketleme modeliyle uyumlu — bkz. README "Neden resmi SDK
değil") ham HTTP kullanıldı. Sadece ANTHROPIC_API_KEY ve
ANTHROPIC_AUTH_TOKEN destekleniyor (ortam değişkeni veya
`~/.config/navigator/env` — bkz. `config.py`); OAuth profili/WIF
çözümlemesi YOK — bu bilinen bir sınırlama.
"""
import json
import urllib.error
import urllib.request
from pathlib import Path

from .config import CredentialResolution, resolve_credentials

API_BASE_URL = "https://api.anthropic.com"
API_VERSION = "2023-06-01"
# ALWAYS use claude-opus-4-8 unless the user explicitly names a different
# model (bkz. claude-api skill) — tarih son eki EKLENMEZ.
DEFAULT_MODEL = "claude-opus-4-8"


class AnthropicError(Exception):
    """Anthropic API'ye bağlanılamadığında, kimlik bilgisi eksikse veya bir istek başarısız olduğunda."""


class AnthropicClient:
    def __init__(
        self,
        base_url: str = API_BASE_URL,
        timeout: float = 30.0,
        credentials_path: Path | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # Sadece testler için: normalde yol os.environ'dan (HOME/
        # XDG_CONFIG_HOME) çözülür — bkz. config.config_path().
        self.credentials_path = credentials_path

    def resolve_credentials(self) -> CredentialResolution:
        """Kimlik bilgisini HER ÇAĞRIDA yeniden çözer (önbelleklenmez).

        Böylece uzun ömürlü bir istemci nesnesi, kullanıcı dosyayı
        oluşturduktan/düzelttikten sonra yeniden başlatmaya gerek kalmadan
        onu görür; maliyet, çağrı başına birkaç yüz baytlık bir dosya
        okuması (dosya yoksa tek bir stat).
        """
        return resolve_credentials(path=self.credentials_path)

    def _auth_headers(self) -> dict:
        values = self.resolve_credentials().values

        api_key = values.get("ANTHROPIC_API_KEY")
        if api_key:
            return {"x-api-key": api_key}

        auth_token = values.get("ANTHROPIC_AUTH_TOKEN")
        if auth_token:
            # OAuth token'lar Authorization: Bearer ile gönderilir (x-api-key
            # ile DEĞİL) ve anthropic-beta: oauth-2025-04-20 header'ı gerekir.
            return {
                "Authorization": f"Bearer {auth_token}",
                "anthropic-beta": "oauth-2025-04-20",
            }

        raise AnthropicError(
            "Kimlik bilgisi yok: ANTHROPIC_API_KEY veya ANTHROPIC_AUTH_TOKEN "
            "ortam değişkeni ya da ~/.config/navigator/env dosyası gerekli."
        )

    def is_available(self) -> bool:
        """Bir kimlik bilgisinin çözülüp çözülmediğini kontrol eder —
        GERÇEK BİR API ÇAĞRISI YAPMAZ. Ollama istemcisinin
        is_available()'ından farklı olarak (bkz. local-runtime/client.py):
        Anthropic API'sinde ücretsiz bir "ping" uç noktası olmadığından,
        gereksiz/anlamsız bir ağ çağrısı yapmak yerine sadece kimlik
        bilgisinin varlığı kontrol ediliyor.
        """
        return bool(self.resolve_credentials().values)

    def generate(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 1024,
        system: str | None = None,
    ) -> dict:
        """POST /v1/messages ile tek turluk bir tamamlama isteği gönderir.

        `send_messages()`'ın tek kullanıcı mesajlı, tool'suz özel hali.
        """
        return self.send_messages(
            [{"role": "user", "content": prompt}], model=model, max_tokens=max_tokens, system=system
        )

    def send_messages(
        self,
        messages: list[dict],
        model: str = DEFAULT_MODEL,
        max_tokens: int = 1024,
        system: str | None = None,
        tools: list[dict] | None = None,
    ) -> dict:
        """POST /v1/messages ile çok turlu bir mesaj listesi gönderir.

        `assistant/` modülünün tool-use döngüsü için: `tools` verilirse
        Claude yanıtında `tool_use` içerik blokları dönebilir
        (`stop_reason: "tool_use"`); çağıran taraf bunları çalıştırıp
        `tool_result` mesajıyla `messages`'a ekleyip tekrar çağırmalı.
        """
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": API_VERSION,
            **self._auth_headers(),
        }
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = tools

        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/v1/messages", data=data, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise AnthropicError(f"Claude API isteği başarısız: {e}") from e
