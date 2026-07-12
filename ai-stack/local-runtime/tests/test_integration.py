import json
import os
import subprocess
import unittest


class TestLocalRuntimeIntegration(unittest.TestCase):
    """Gerçek Ollama kurulumuna karşı çalışır — Ollama bu makinede kurulu ve
    çalışıyor (systemd servisi), ama önerilen model (llama3.2:3b) henüz
    indirilmedi (ayrı bir onay gerektiriyor, bkz. README)."""

    def test_status_cli_runs_with_real_ollama_installed(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(
            ["python3", "-m", "local_runtime"],
            cwd=here,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertIn(report["hardware_tier"], ("minimal", "low", "mid", "high"))
        self.assertTrue(report["ollama_available"])
        self.assertEqual(report["installed_models"], [])
        self.assertFalse(report["model_ready"])

    def test_prompt_cli_reports_model_not_installed(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(
            ["python3", "-m", "local_runtime", "--prompt", "merhaba"],
            cwd=here,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "unavailable")
        self.assertEqual(report["reason"], "model_not_installed")
        self.assertEqual(report["model"], "llama3.2:3b")


if __name__ == "__main__":
    unittest.main()
