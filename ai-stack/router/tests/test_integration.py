import json
import os
import subprocess
import unittest


class TestRouterIntegration(unittest.TestCase):
    """router -> local-runtime -> hardware-probe zincirinin gerçek subprocess'lerle
    uçtan uca çalıştığını doğrular (bu makinede Ollama kurulu değil)."""

    def test_route_cli_runs_end_to_end(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(
            ["python3", "-m", "router", "--prompt", "Navigator'da workspace nasıl değiştiririm?"],
            cwd=here,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertIn(report["hardware_tier"], ("minimal", "low", "mid", "high"))
        # Ollama bu ortamda kurulu değil -> model_ready False -> her zaman cloud
        self.assertFalse(report["model_ready"])
        self.assertEqual(report["route"], "cloud")


if __name__ == "__main__":
    unittest.main()
