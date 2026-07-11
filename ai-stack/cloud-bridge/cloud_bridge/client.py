"""Anthropic Claude API için ince istemci — stdlib-only (harici bağımlılık yok).

Not: Resmi `anthropic` Python SDK'sı kimlik bilgisi çözümlemesini (API key →
auth token → OAuth profili → Workload Identity Federation → disk profili)
otomatik yapar ve önerilen yoldur. Burada diğer ai-stack modülleriyle aynı
stdlib-only ilkesi korunmak istendiği için (Navigator OS'un rpm-ostree/
Containerfile paketleme modeliyle uyumlu — bkz. README "Neden resmi SDK
değil") ham HTTP kullanıldı. Sadece ANTHROPIC_API_KEY ve
ANTHROPIC_AUTH_TOKEN ortam değişkenleri destekleniyor; OAuth profili/WIF
çözümlemesi YOK — bu bilinen bir sınırlama.
"""
import json
import os
import urllib.error
import urllib.request

API_BASE_URL = "https://api.anthropic.com"
API_VERSION = "2023-06-01"
# ALWAYS use claude-opus-4-8 unless the user explicitly names a different
# model (bkz. claude-api skill) — tarih son eki EKLENMEZ.
DEFAULT_MODEL = "claude-opus-4-8"


class AnthropicError(Exception):
    """Anthropic API'ye bağlanılamadığında, kimlik bilgisi eksikse veya bir istek başarısız olduğunda."""


class AnthropicClient:
    def __init__(self, base_url: str = API_BASE_URL, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _auth_headers(self) -> dict:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            return {"x-api-key": api_key}

        auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN")
        if auth_token:
            # OAuth token'lar Authorization: Bearer ile gönderilir (x-api-key
            # ile DEĞİL) ve anthropic-beta: oauth-2025-04-20 header'ı gerekir.
            return {
                "Authorization": f"Bearer {auth_token}",
                "anthropic-beta": "oauth-2025-04-20",
            }

        raise AnthropicError(
            "Kimlik bilgisi yok: ANTHROPIC_API_KEY veya ANTHROPIC_AUTH_TOKEN "
            "ortam değişkenlerinden biri gerekli."
        )

    def is_available(self) -> bool:
        """Bir kimlik bilgisi ortam değişkeninin ayarlı olup olmadığını
        kontrol eder — GERÇEK BİR API ÇAĞRISI YAPMAZ. Ollama istemcisinin
        is_available()'ından farklı olarak (bkz. local-runtime/client.py):
        Anthropic API'sinde ücretsiz bir "ping" uç noktası olmadığından,
        gereksiz/anlamsız bir ağ çağrısı yapmak yerine sadece ortam
        değişkeni varlığı kontrol ediliyor.
        """
        return bool(
            os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        )

    def generate(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 1024,
        system: str | None = None,
    ) -> dict:
        """POST /v1/messages ile tek turluk bir tamamlama isteği gönderir.

        Bu metod bu ortamda GERÇEK bir çağrı ile test edilmedi — kimlik
        bilgisi yok ve gerçek bir Claude API çağrısı maliyetli olduğundan
        onaysız yapılmadı (bkz. README "Kapsam dışı").
        """
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": API_VERSION,
            **self._auth_headers(),
        }
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/v1/messages", data=data, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise AnthropicError(f"Claude API isteği başarısız: {e}") from e
