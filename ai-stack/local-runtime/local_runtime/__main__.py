"""CLI: `python3 -m local_runtime [--pretty] [--hardware-probe-path PATH]` (durum) veya
`python3 -m local_runtime --prompt "..." [--hardware-probe-path PATH]` (gerçek istek).
"""
import argparse
import json
import sys

from .client import OllamaClient, OllamaError
from .status import SCHEMA_VERSION, build_status_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Navigator OS yerel model runtime durumu veya isteği (Ollama + hardware tier)."
    )
    parser.add_argument("--pretty", action="store_true", help="JSON çıktısını girintili yazdır")
    parser.add_argument(
        "--hardware-probe-path",
        default="../hardware-probe",
        help="ai-stack/hardware-probe dizininin yolu (varsayılan: ../hardware-probe)",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Verilirse önerilen model ile gerçek bir Ollama isteği gönderir (yoksa sadece durum raporlanır)",
    )
    args = parser.parse_args()
    indent = 2 if args.pretty else None

    try:
        status = build_status_report(hardware_probe_cwd=args.hardware_probe_path)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1

    if args.prompt is None:
        print(json.dumps(status, indent=indent, ensure_ascii=False))
        return 0

    report = {
        "schema_version": SCHEMA_VERSION,
        "provider": "ollama",
        "hardware_tier": status["hardware_tier"],
        "prompt_preview": args.prompt[:80],
    }

    recommendation = status["recommended_model"]
    if recommendation is None:
        report["status"] = "unavailable"
        report["reason"] = "no_local_model_recommended"
    elif not status["ollama_available"]:
        report["status"] = "unavailable"
        report["reason"] = "ollama_not_running"
        report["model"] = recommendation["model"]
    elif not status["model_ready"]:
        report["status"] = "unavailable"
        report["reason"] = "model_not_installed"
        report["model"] = recommendation["model"]
    else:
        model = recommendation["model"]
        report["model"] = model
        try:
            response = OllamaClient().generate(model, args.prompt)
        except OllamaError as e:
            report["status"] = "error"
            report["error"] = str(e)
            print(json.dumps(report, indent=indent, ensure_ascii=False), file=sys.stderr)
            return 1
        report["status"] = "ok"
        report["content"] = response.get("response", "")

    print(json.dumps(report, indent=indent, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
