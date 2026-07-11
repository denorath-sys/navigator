import json
import os
import subprocess
import unittest


class TestLocalRuntimeIntegration(unittest.TestCase):
    """Ollama kurulu değilken CLI'ın çökmeden düzgün rapor ürettiğini doğrular
    (gerçek hardware-probe subprocess'i + bu makinede olmayan Ollama)."""

    def test_status_cli_runs_without_ollama_installed(self):
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
        self.assertFalse(report["ollama_available"])
        self.assertEqual(report["installed_models"], [])


if __name__ == "__main__":
    unittest.main()
