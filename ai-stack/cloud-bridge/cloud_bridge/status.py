"""Reports the credential status and the default model information."""
from .client import AnthropicClient, DEFAULT_MODEL

SCHEMA_VERSION = "0.1"


def build_status_report(client: AnthropicClient | None = None) -> dict:
    client = client or AnthropicClient()
    resolution = client.resolve_credentials()

    # The credential ITSELF never enters the report; only where it came from
    # (or why it did not). `credentials_file` is always written — even when the
    # file does not exist, so the user can see from the `--pretty` output which
    # path they need to create.
    return {
        "schema_version": SCHEMA_VERSION,
        "provider": "anthropic",
        "default_model": DEFAULT_MODEL,
        "credentials_configured": bool(resolution.values),
        "credentials_source": resolution.source,
        "credentials_file": str(resolution.path),
        "credentials_file_problem": resolution.problem,
    }
