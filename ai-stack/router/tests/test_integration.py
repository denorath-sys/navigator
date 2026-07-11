import json
import os
import subprocess
import unittest


class TestRouterIntegration(unittest.TestCase):
    """router -> local-runtime -> hardware-probe VE router -> cloud-bridge
    zincirlerinin gerçek subprocess'lerle uçtan uca çalıştığını doğrular
    (bu makinede Ollama kurulu değil ve Claude API kimlik bilgisi yok)."""

    def test_route_cli_runs_end_to_end(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = {k: v for k, v in os.environ.items() if not k.startswith("ANTHROPIC_")}
        result = subprocess.run(
            ["python3", "-m", "router", "--prompt", "Navigator'da workspace nasıl değiştiririm?"],
            cwd=here,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertIn(report["hardware_tier"], ("minimal", "low", "mid", "high"))
        # Ollama bu ortamda kurulu değil -> model_ready False -> her zaman cloud
        self.assertFalse(report["model_ready"])
        self.assertEqual(report["route"], "cloud")

        # route == "cloud" olduğundan cloud-bridge gerçekten çağrılmış olmalı
        self.assertIn("cloud_bridge", report)
        self.assertEqual(report["cloud_bridge"]["status"], "unavailable")
        self.assertEqual(report["cloud_bridge"]["reason"], "credentials_not_configured")


if __name__ == "__main__":
    unittest.main()
