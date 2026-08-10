import json
import os
import subprocess
import unittest


class TestLocalRuntimeIntegration(unittest.TestCase):
    """Runs against a real Ollama installation AND a really pulled model
    (llama3.2:3b) — fully ready on this machine (ollama_available: true,
    model_ready: true)."""

    def test_status_cli_reports_model_ready(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(
            ["python3", "-m", "local_runtime"],
            cwd=here,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertIn(report["hardware_tier"], ("minimal", "low", "mid", "high"))
        self.assertTrue(report["ollama_available"])
        self.assertIn("llama3.2:3b", report["installed_models"])
        self.assertTrue(report["model_ready"])

    def test_prompt_cli_gets_real_generation(self):
        """A real Ollama generate() call — with a generous timeout margin,
        since the model may be loaded into memory and infer on CPU."""
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(
            ["python3", "-m", "local_runtime", "--prompt", "Reply with the single word 'hello'."],
            cwd=here,
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["model"], "llama3.2:3b")
        self.assertIsInstance(report["content"], str)
        self.assertGreater(len(report["content"]), 0)

    def test_converse_cli_gets_real_tool_call(self):
        """A real Ollama /api/chat call with tool-calling — verifying that
        llama3.2:3b genuinely produces a tool_use request."""
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": "Call the hardware_tier tool to find out this machine's hardware tier.",
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "hardware_tier",
                        "description": "Returns the hardware tier information.",
                        "parameters": {"type": "object", "properties": {}, "required": []},
                    },
                }
            ],
        }
        result = subprocess.run(
            ["python3", "-m", "local_runtime", "--converse"],
            cwd=here,
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        response = json.loads(result.stdout)
        tool_calls = response["message"].get("tool_calls", [])
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["function"]["name"], "hardware_tier")


if __name__ == "__main__":
    unittest.main()
