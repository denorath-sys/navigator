import json
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from router.cloud import call_cloud_bridge


class TestCallCloudBridge(unittest.TestCase):
    @patch("router.cloud.subprocess.run")
    def test_sends_correct_command_and_parses_json(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"status": "unavailable", "reason": "credentials_not_configured"})
        )
        result = call_cloud_bridge("merhaba", cwd="../cloud-bridge")

        self.assertEqual(result["status"], "unavailable")
        args, kwargs = mock_run.call_args
        self.assertEqual(args[0], ["python3", "-m", "cloud_bridge", "--prompt", "merhaba"])
        self.assertEqual(kwargs["cwd"], "../cloud-bridge")
        self.assertTrue(kwargs["check"])

    @patch("router.cloud.subprocess.run")
    def test_propagates_called_process_error(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "cloud_bridge")
        with self.assertRaises(subprocess.CalledProcessError):
            call_cloud_bridge("merhaba")


if __name__ == "__main__":
    unittest.main()
