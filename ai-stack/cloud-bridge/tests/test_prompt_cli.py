import json
import os
import subprocess
import unittest


class TestPromptCLI(unittest.TestCase):
    """`python3 -m cloud_bridge --prompt ...` yolunu gerçek subprocess ile test eder
    (kimlik bilgisi yok -> graceful "unavailable" durumu, exit 0)."""

    def test_prompt_without_credentials_is_graceful(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = {k: v for k, v in os.environ.items() if not k.startswith("ANTHROPIC_")}
        result = subprocess.run(
            ["python3", "-m", "cloud_bridge", "--prompt", "merhaba"],
            cwd=here,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "unavailable")
        self.assertEqual(report["reason"], "credentials_not_configured")
        self.assertEqual(report["model"], "claude-opus-4-8")


HAS_CLOUD_CREDENTIALS = bool(
    os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
)


class TestPromptCLICredentialed(unittest.TestCase):
    """Kimlik bilgisi mevcutsa (örn. .env.local source edilmişse) GERÇEK bir
    Claude API çağrısı yapar — kimlik bilgisi yoksa (CI dahil) atlanır."""

    @unittest.skipUnless(
        HAS_CLOUD_CREDENTIALS, "ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN ayarlı değil"
    )
    def test_prompt_with_credentials_gets_real_response(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(
            [
                "python3", "-m", "cloud_bridge",
                "--prompt", "Tek kelimeyle cevap ver: Türkiye'nin başkenti neresi?",
                "--max-tokens", "20",
            ],
            cwd=here,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "ok")
        self.assertIn("ankara", report["content"].lower())


if __name__ == "__main__":
    unittest.main()
