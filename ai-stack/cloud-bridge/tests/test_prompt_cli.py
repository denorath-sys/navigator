import json
import os
import subprocess
import tempfile
import unittest

from cloud_bridge.config import resolve_credentials


class TestPromptCLI(unittest.TestCase):
    """`python3 -m cloud_bridge --prompt ...` yolunu gerçek subprocess ile test eder
    (kimlik bilgisi yok -> graceful "unavailable" durumu, exit 0)."""

    def test_prompt_without_credentials_is_graceful(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = {k: v for k, v in os.environ.items() if not k.startswith("ANTHROPIC_")}
        # HOME de boşaltılıyor: kimlik bilgisi artık ~/.config/navigator/env'den
        # de okunabildiği için, geliştiricinin gerçek dosyası bu testi
        # "unavailable" olmaktan çıkarırdı.
        env["HOME"] = os.path.join(tempfile.gettempdir(), "navigator-test-empty-home")
        env.pop("XDG_CONFIG_HOME", None)
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


# Artık sadece ortam değişkenine bakmıyor: ~/.config/navigator/env de
# geçerli bir kaynak, ve bu testin "gerçek API'ye git" kapısı üretimin
# kullandığı çözümlemenin AYNISI olmalı.
HAS_CLOUD_CREDENTIALS = bool(resolve_credentials().values)


class TestPromptCLICredentialed(unittest.TestCase):
    """Kimlik bilgisi mevcutsa (.env.local source edilmişse ya da
    ~/.config/navigator/env varsa) GERÇEK bir Claude API çağrısı yapar —
    kimlik bilgisi yoksa (CI dahil) atlanır."""

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
