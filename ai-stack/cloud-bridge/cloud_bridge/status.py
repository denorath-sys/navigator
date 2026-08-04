"""Kimlik bilgisi durumunu ve varsayılan model bilgisini raporlar."""
from .client import AnthropicClient, DEFAULT_MODEL

SCHEMA_VERSION = "0.1"


def build_status_report(client: AnthropicClient | None = None) -> dict:
    client = client or AnthropicClient()
    resolution = client.resolve_credentials()

    # Kimlik bilgisinin KENDİSİ asla rapora girmez; sadece nereden geldiği
    # (veya neden gelmediği). `credentials_file` her zaman yazılıyor —
    # dosya yokken bile, kullanıcının hangi yolu oluşturması gerektiğini
    # `--pretty` çıktısından görebilmesi için.
    return {
        "schema_version": SCHEMA_VERSION,
        "provider": "anthropic",
        "default_model": DEFAULT_MODEL,
        "credentials_configured": bool(resolution.values),
        "credentials_source": resolution.source,
        "credentials_file": str(resolution.path),
        "credentials_file_problem": resolution.problem,
    }
