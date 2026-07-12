import json
import os
import subprocess
import unittest


class TestRouterIntegration(unittest.TestCase):
    """router -> local-runtime -> hardware-probe VE router -> cloud-bridge
    zincirlerinin GERÇEK subprocess'lerle uçtan uca çalıştığını doğrular.

    Bu makinede Ollama kurulu, çalışıyor ve önerilen model (llama3.2:3b)
    indirildi (model_ready: true) — basit istekler artık gerçekten yerelde
    üretiliyor. Karmaşık istekler ise (tier="low" düşük kapasiteli
    sayıldığından) yine cloud-bridge'e düşüyor; Claude API kimlik bilgisi
    olmadığından o yol "unavailable" raporluyor.
    """

    def _run_router(self, prompt: str) -> dict:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = {k: v for k, v in os.environ.items() if not k.startswith("ANTHROPIC_")}
        result = subprocess.run(
            ["python3", "-m", "router", "--prompt", prompt],
            cwd=here,
            capture_output=True,
            text=True,
            env=env,
            timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_simple_prompt_routes_local_with_real_generation(self):
        report = self._run_router("Sadece 'merhaba' kelimesiyle cevap ver.")
        self.assertIn(report["hardware_tier"], ("minimal", "low", "mid", "high"))
        self.assertTrue(report["model_ready"])
        self.assertEqual(report["route"], "local")

        self.assertIn("local_runtime", report)
        self.assertNotIn("cloud_bridge", report)
        self.assertEqual(report["local_runtime"]["status"], "ok")
        self.assertEqual(report["local_runtime"]["model"], "llama3.2:3b")
        self.assertIsInstance(report["local_runtime"]["content"], str)
        self.assertGreater(len(report["local_runtime"]["content"]), 0)

    def test_complex_prompt_routes_cloud(self):
        # tier="low" bu makinede "düşük kapasiteli" sayıldığından, model
        # hazır olsa bile karmaşık (uzun) istekler cloud-bridge'e düşer.
        long_prompt = " ".join(["kelime"] * 50)
        report = self._run_router(long_prompt)
        self.assertEqual(report["complexity"], "complex")
        self.assertEqual(report["route"], "cloud")

        self.assertIn("cloud_bridge", report)
        self.assertNotIn("local_runtime", report)
        self.assertEqual(report["cloud_bridge"]["status"], "unavailable")
        self.assertEqual(report["cloud_bridge"]["reason"], "credentials_not_configured")


if __name__ == "__main__":
    unittest.main()
