import json
import os
import subprocess
import unittest

from router.status import route_request


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

    def test_local_route_calls_real_local_runtime_subprocess(self):
        """Karar adımına sahte 'model hazır' durumu enjekte edip route="local"
        zorlanır; gerçek local_runtime subprocess'i yine de GERÇEK Ollama
        durumunu (bu makinede kurulu değil) sorgular ve doğru raporlar."""
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        fake_status = {"hardware_tier": "mid", "model_ready": True}
        report = route_request(
            "basit bir soru",
            status=fake_status,
            local_runtime_cwd=os.path.join(here, "..", "local-runtime"),
        )
        self.assertEqual(report["route"], "local")
        self.assertIn("local_runtime", report)
        self.assertEqual(report["local_runtime"]["status"], "unavailable")
        self.assertEqual(report["local_runtime"]["reason"], "ollama_not_running")
        self.assertNotIn("cloud_bridge", report)


if __name__ == "__main__":
    unittest.main()
