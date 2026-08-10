"""A thin client for the Ollama REST API — stdlib-only (no external dependencies).

Even when Ollama itself is not installed (it was not, in this environment —
see the project constraints) this client can be tested with mocked HTTP
(bkz. tests/test_client.py).
"""
import json
import urllib.error
import urllib.request


class OllamaError(Exception):
    """Raised when Ollama cannot be reached or a request fails."""


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, timeout: float | None = None) -> dict:
        with urllib.request.urlopen(f"{self.base_url}{path}", timeout=timeout or self.timeout) as resp:
            return json.loads(resp.read())

    def _post(self, path: str, payload: dict, timeout: float | None = None) -> dict:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout or self.timeout) as resp:
            return json.loads(resp.read())

    def is_available(self) -> bool:
        try:
            self._get("/api/version")
            return True
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def list_models(self) -> list[str]:
        try:
            data = self._get("/api/tags")
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise OllamaError(f"Could not connect to Ollama: {e}") from e
        return [m["name"] for m in data.get("models", [])]

    def generate(self, model: str, prompt: str, stream: bool = False, timeout: float = 300.0) -> dict:
        """Loading the model into memory and running inference on CPU
        (especially on the first call) can take minutes — the default timeout
        is far higher (300s) than for metadata endpoints such as
        `is_available()`/`list_models()`."""
        try:
            return self._post(
                "/api/generate",
                {"model": model, "prompt": prompt, "stream": stream},
                timeout=timeout,
            )
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise OllamaError(f"Ollama generate request failed: {e}") from e

    def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        timeout: float = 300.0,
    ) -> dict:
        """Send a multi-turn, tool-calling-capable request with `/api/chat`
        (verified on the real machine with `llama3.2:3b` — the model returns
        `{"function": {"name", "arguments"}}` inside `message.tool_calls`; to
        feed the result back, appending a `{"role": "tool", "content": ...}`
        message is enough, no `tool_call_id` matching is required)."""
        payload = {"model": model, "messages": messages, "stream": stream}
        if tools:
            payload["tools"] = tools
        try:
            return self._post("/api/chat", payload, timeout=timeout)
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise OllamaError(f"Ollama chat request failed: {e}") from e
