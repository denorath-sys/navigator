"""HTTP+SSE transport için Bearer token kimlik doğrulaması — stdlib-only.

Tasarım ilkesi: kimliksiz çalışma YOK. `http_transport.run_http_server()`
bir token verilmediğinde otomatik üretir ve stderr'e yazdırır — sunucunun
sessizce açık kapı olarak çalışması hiçbir zaman mümkün değil (Jupyter'ın
notebook token'ı gibi).
"""
import hmac
import secrets


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def extract_bearer_token(authorization_header: str | None) -> str | None:
    """`Authorization: Bearer <token>` header'ından token'ı çıkarır."""
    if not authorization_header:
        return None
    parts = authorization_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def tokens_match(provided: str | None, expected: str) -> bool:
    """Zamanlama saldırısına dayanıklı karşılaştırma (`hmac.compare_digest`)."""
    if provided is None:
        return False
    return hmac.compare_digest(provided, expected)
