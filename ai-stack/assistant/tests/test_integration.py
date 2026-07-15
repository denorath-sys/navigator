import json
import os
import subprocess
import unittest

from assistant.mcp_client import MCPClient

HAS_CLOUD_CREDENTIALS = bool(
    os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
)


class TestAssistantIntegration(unittest.TestCase):
    """assistant -> router -> (local-runtime | cloud-bridge) -> mcp-tools
    zincirinin GERÇEK subprocess'lerle uçtan uca çalıştığını doğrular.

    Yerel yol (Ollama kurulu/model hazır olduğundan) her zaman gerçek
    çalışır. Bulut yolu + gerçek tool-use döngüsü, ANTHROPIC_API_KEY/
    ANTHROPIC_AUTH_TOKEN ortamda yoksa (CI dahil) otomatik `skip` olur.
    """

    def _run_cli(self, prompt: str, extra_args: list[str] | None = None) -> dict:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(
            ["python3", "-m", "assistant", "--prompt", prompt, *(extra_args or [])],
            cwd=here,
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_simple_prompt_routes_local_with_real_generation(self):
        report = self._run_cli("Sadece 'merhaba' kelimesiyle cevap ver.")
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["route"], "local")
        self.assertEqual(report["tool_calls"], [])
        self.assertIsInstance(report["content"], str)
        self.assertGreater(len(report["content"]), 0)

    @unittest.skipUnless(
        HAS_CLOUD_CREDENTIALS, "ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN ayarlı değil"
    )
    def test_complex_prompt_routes_cloud_and_uses_real_hardware_tool(self):
        long_prompt = (
            "Bu makinede kaç tane CPU çekirdeği var, toplam RAM ne kadar, ve "
            "ayrık bir grafik kartı var mı yok mu, bunların hepsini lütfen "
            "gerçek donanım tespit aracını kullanarak öğren ve bana net bir "
            "şekilde madde madde özetle, sakın tahmin etme, sadece aracın "
            "döndürdüğü gerçek verilere dayan ve kısa tut."
        )
        report = self._run_cli(long_prompt)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["route"], "cloud")
        self.assertEqual(report["tool_calls"], [{"name": "hardware_tier", "input": {}}])
        self.assertIn("6", report["content"])  # gerçek çekirdek sayısı
        self.assertIn("15", report["content"])  # gerçek RAM (~15.4 GB)

    @unittest.skipUnless(
        HAS_CLOUD_CREDENTIALS, "ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN ayarlı değil"
    )
    def test_mcp_client_and_run_cloud_turn_real_end_to_end(self):
        """CLI'ı atlayıp iç API'yi doğrudan kullanarak (gerçek mcp-tools
        subprocess'i + gerçek Claude API) aynı akışı doğrular."""
        from assistant.conversation import run_cloud_turn

        with MCPClient(cwd="../mcp-tools") as client:
            result = run_cloud_turn(
                "Bu makinenin donanım tier'ı nedir? Aracı kullanarak gerçekten öğren.",
                client,
            )
        self.assertEqual(result["route"], "cloud")
        self.assertTrue(any(tc["name"] == "hardware_tier" for tc in result["tool_calls"]))
        self.assertIn("low", result["content"].lower())


if __name__ == "__main__":
    unittest.main()
