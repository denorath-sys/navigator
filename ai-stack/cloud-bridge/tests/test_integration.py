import json
import os
import subprocess
import unittest


class TestCloudBridgeIntegration(unittest.TestCase):
    """Gerçek CLI'ın kimlik bilgisi olmadan çökmeden çalıştığını doğrular
    (hiçbir gerçek Claude API çağrısı yapılmaz)."""

    def test_status_cli_runs_without_credentials(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = {k: v for k, v in os.environ.items() if not k.startswith("ANTHROPIC_")}
        result = subprocess.run(
            ["python3", "-m", "cloud_bridge"],
            cwd=here,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report["credentials_configured"])
        self.assertEqual(report["default_model"], "claude-opus-4-8")


if __name__ == "__main__":
    unittest.main()
