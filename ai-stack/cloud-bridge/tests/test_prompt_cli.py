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


if __name__ == "__main__":
    unittest.main()
