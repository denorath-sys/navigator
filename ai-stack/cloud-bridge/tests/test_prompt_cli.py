import json
import os
import subprocess
import tempfile
import unittest

from cloud_bridge.config import resolve_credentials


class TestPromptCLI(unittest.TestCase):
    """Tests the `python3 -m cloud_bridge --prompt ...` path with a real subprocess
    (kimlik bilgisi yok -> graceful "unavailable" durumu, exit 0)."""

    def test_prompt_without_credentials_is_graceful(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = {k: v for k, v in os.environ.items() if not k.startswith("ANTHROPIC_")}
        # HOME is emptied too: because the credential can now also be read
        # from ~/.config/navigator/env, the developer's real file would stop
        # this test from being "unavailable".
        env["HOME"] = os.path.join(tempfile.gettempdir(), "navigator-test-empty-home")
        env.pop("XDG_CONFIG_HOME", None)
        result = subprocess.run(
            ["python3", "-m", "cloud_bridge", "--prompt", "hello"],
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


# It no longer looks only at the environment variable: ~/.config/navigator/env
# is a valid source too, and this test's "go to the real API" gate must be the
# SAME resolution that production uses.
HAS_CLOUD_CREDENTIALS = bool(resolve_credentials().values)


class TestPromptCLICredentialed(unittest.TestCase):
    """Makes a REAL Claude API call if credentials are present (.env.local
    sourced, or ~/.config/navigator/env exists) — skipped when there are no
    credentials (including in CI)."""

    @unittest.skipUnless(
        HAS_CLOUD_CREDENTIALS, "ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN is not set"
    )
    def test_prompt_with_credentials_gets_real_response(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(
            [
                "python3", "-m", "cloud_bridge",
                "--prompt", "Answer in one word: what is the capital of Turkey?",
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
