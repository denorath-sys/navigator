"""Bearer token authentication for the HTTP+SSE transport — stdlib-only.

Design principle: NO unauthenticated operation. When no token is given,
`http_transport.run_http_server()` generates one automatically and prints it
to stderr — it is never possible for the server to run silently as an open
door (the same idea as Jupyter's notebook token).
"""
import hmac
import secrets


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def extract_bearer_token(authorization_header: str | None) -> str | None:
    """Extract the token from an `Authorization: Bearer <token>` header."""
    if not authorization_header:
        return None
    parts = authorization_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def tokens_match(provided: str | None, expected: str) -> bool:
    """A timing-attack-resistant comparison (`hmac.compare_digest`)."""
    if provided is None:
        return False
    return hmac.compare_digest(provided, expected)
