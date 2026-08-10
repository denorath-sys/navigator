import json
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from router.local import call_local_runtime


class TestCallLocalRuntime(unittest.TestCase):
    @patch("router.local.subprocess.run")
    def test_sends_correct_command_and_parses_json(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"status": "unavailable", "reason": "ollama_not_running"})
        )
        result = call_local_runtime("hello", cwd="../local-runtime")

        self.assertEqual(result["status"], "unavailable")
        args, kwargs = mock_run.call_args
        self.assertEqual(args[0], ["python3", "-m", "local_runtime", "--prompt", "hello"])
        self.assertEqual(kwargs["cwd"], "../local-runtime")
        self.assertTrue(kwargs["check"])

    @patch("router.local.subprocess.run")
    def test_propagates_called_process_error(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "local_runtime")
        with self.assertRaises(subprocess.CalledProcessError):
            call_local_runtime("hello")


if __name__ == "__main__":
    unittest.main()
