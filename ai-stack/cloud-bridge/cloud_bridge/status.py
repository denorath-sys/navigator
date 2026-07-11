"""Kimlik bilgisi durumunu ve varsayılan model bilgisini raporlar."""
from .client import AnthropicClient, DEFAULT_MODEL

SCHEMA_VERSION = "0.1"


def build_status_report(client: AnthropicClient | None = None) -> dict:
    client = client or AnthropicClient()
    credentials_configured = client.is_available()

    return {
        "schema_version": SCHEMA_VERSION,
        "provider": "anthropic",
        "default_model": DEFAULT_MODEL,
        "credentials_configured": credentials_configured,
    }
