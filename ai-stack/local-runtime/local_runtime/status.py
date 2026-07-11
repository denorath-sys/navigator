"""hardware-probe çıktısını ve Ollama durumunu tek bir raporda birleştirir."""
import json
import subprocess

from .client import OllamaClient
from .models import recommend_model

SCHEMA_VERSION = "0.1"
HARDWARE_PROBE_CMD = ["python3", "-m", "hardware_probe"]


def get_hardware_tier(cwd: str | None = None) -> dict:
    """ai-stack/hardware-probe CLI'ını çalıştırıp tier raporunu döner.

    İki modül ayrı paketler olduğundan (bkz. ai-stack/README.md mimarisi)
    doğrudan Python import yerine CLI üzerinden konuşuluyor — bu, gerçek
    sistemde ayrı süreçler olarak çalışacakları şekle daha yakın.
    """
    result = subprocess.run(
        HARDWARE_PROBE_CMD, cwd=cwd, capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def build_status_report(hardware_probe_cwd: str | None = None, ollama_client=None) -> dict:
    client = ollama_client or OllamaClient()
    hw_report = get_hardware_tier(cwd=hardware_probe_cwd)
    tier = hw_report["tier"]
    recommendation = recommend_model(tier)

    ollama_available = client.is_available()
    installed_models = client.list_models() if ollama_available else []

    model_ready = bool(
        recommendation and ollama_available and recommendation["model"] in installed_models
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "hardware_tier": tier,
        "recommended_model": recommendation,
        "ollama_available": ollama_available,
        "installed_models": installed_models,
        "model_ready": model_ready,
    }
