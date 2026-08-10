"""A thin client for the Anthropic Claude API — stdlib-only (no external dependencies).

Note: the official `anthropic` Python SDK does credential resolution (API key →
auth token → OAuth profili → Workload Identity Federation → disk profili)
automatically and is the recommended path. Raw HTTP is used here because the
same stdlib-only principle as the other ai-stack modules was to be preserved
Containerfile paketleme modeliyle uyumlu — bkz. README "Neden resmi SDK
pip dependencies). Only ANTHROPIC_API_KEY and ANTHROPIC_AUTH_TOKEN are
supported (from an environment variable or
`~/.config/navigator/env` — bkz. `config.py`); OAuth profili/WIF
resolution — a known limitation.
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
    """Raised when the Anthropic API cannot be reached, credentials are missing, or a request fails."""


class AnthropicClient:
    def __init__(
        self,
        base_url: str = API_BASE_URL,
        timeout: float = 30.0,
        credentials_path: Path | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # For tests only: normally the path is resolved from os.environ
        # (HOME/XDG_CONFIG_HOME) — see config.config_path().
        self.credentials_path = credentials_path

    def resolve_credentials(self) -> CredentialResolution:
        """Re-resolve the credential ON EVERY CALL (it is not cached).

        This way a long-lived client object sees the file after the user
        creates or fixes it, without needing a restart; the cost is reading a
        file of a few hundred bytes per call (a single stat if the file does
        not exist).
        """
        return resolve_credentials(path=self.credentials_path)

    def _auth_headers(self) -> dict:
        values = self.resolve_credentials().values

        api_key = values.get("ANTHROPIC_API_KEY")
        if api_key:
            return {"x-api-key": api_key}

        auth_token = values.get("ANTHROPIC_AUTH_TOKEN")
        if auth_token:
            # OAuth tokens are sent with Authorization: Bearer (NOT with
            # x-api-key) and require the anthropic-beta: oauth-2025-04-20 header.
            return {
                "Authorization": f"Bearer {auth_token}",
                "anthropic-beta": "oauth-2025-04-20",
            }

        raise AnthropicError(
            "No credentials: an ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN "
            "environment variable, or a ~/.config/navigator/env file, is required."
        )

    def is_available(self) -> bool:
        """Check whether a credential resolves — it MAKES NO REAL API CALL.
        Unlike the Ollama client's is_available() (see
        local-runtime/client.py): because the Anthropic API has no free "ping"
        endpoint, only the presence of a credential is checked rather than
        making a pointless network call.
        """
        return bool(self.resolve_credentials().values)

    def generate(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 1024,
        system: str | None = None,
    ) -> dict:
        """Send a single-turn completion request with POST /v1/messages.

        A special case of `send_messages()` with one user message and no tools.
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
        """Send a multi-turn message list with POST /v1/messages.

        For the `assistant/` module's tool-use loop: if `tools` is given,
        Claude's response can contain `tool_use` content blocks
        (`stop_reason: "tool_use"`); the caller must execute them, append them
        to `messages` as a `tool_result` message, and call again.
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
            raise AnthropicError(f"Claude API request failed: {e}") from e
