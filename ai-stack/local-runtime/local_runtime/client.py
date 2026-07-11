"""Ollama REST API için ince istemci — stdlib-only (harici bağımlılık yok).

Ollama'nın kendisi kurulu olmasa da (bu ortamda kurulu değil — bkz. proje
kısıtları) bu istemci mock'lanmış HTTP yanıtlarıyla test edilebilir
(bkz. tests/test_client.py).
"""
import json
import urllib.error
import urllib.request


class OllamaError(Exception):
    """Ollama'ya bağlanılamadığında veya bir istek başarısız olduğunda."""


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str) -> dict:
        with urllib.request.urlopen(f"{self.base_url}{path}", timeout=self.timeout) as resp:
            return json.loads(resp.read())

    def _post(self, path: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as resp:
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
            raise OllamaError(f"Ollama'ya bağlanılamadı: {e}") from e
        return [m["name"] for m in data.get("models", [])]

    def generate(self, model: str, prompt: str, stream: bool = False) -> dict:
        try:
            return self._post("/api/generate", {"model": model, "prompt": prompt, "stream": stream})
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise OllamaError(f"Ollama generate isteği başarısız: {e}") from e
