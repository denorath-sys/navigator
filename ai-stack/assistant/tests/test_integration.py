import json
import os
import subprocess
import tempfile
import unittest

from assistant.mcp_client import MCPClient

HAS_CLOUD_CREDENTIALS = bool(
    os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
)


class TestAssistantIntegration(unittest.TestCase):
    """Verifies that the assistant -> router -> (local-runtime |
    cloud-bridge) -> mcp-tools chain works end to end with REAL subprocesses.

    The local path always runs for real (Ollama is installed and the model is
    ready). The cloud path + the real tool-use loop `skip` automatically when
    ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN is absent from the environment
    (including in CI).
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

    def _run_cli_until(self, prompt, predicate, extra_args=None, max_attempts=3) -> dict:
        """The local 3B model's tool-use output was observed in real testing
        to be inherently stochastic (it sometimes produces raw JSON text
        instead of structured tool_calls) — this is not a code bug but a known
        limitation of small models (see assistant/README.md). Tests that depend
        on content quality therefore retry a limited number of times; the
        security tests (the write tool is never shown or executed) DO NOT use
        this, being deterministic."""
        report = None
        for _ in range(max_attempts):
            report = self._run_cli(prompt, extra_args)
            if predicate(report):
                return report
        return report

    def test_simple_prompt_routes_local_with_real_generation(self):
        """In real testing the 3B model occasionally makes unnecessary tool
        calls even on simple requests (a weakness of small models) — so
        tool_calls does NOT HAVE to be empty, but it must NEVER contain a
        write or delete tool (see LOCAL_SAFE_TOOL_NAMES, the defence against
        the hallucinated write_file call caught in real testing)."""
        from assistant.conversation import LOCAL_SAFE_TOOL_NAMES

        report = self._run_cli("Reply with the single word 'hello'.")
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["route"], "local")
        for call in report["tool_calls"]:
            self.assertIn(call["name"], LOCAL_SAFE_TOOL_NAMES)
        self.assertIsInstance(report["content"], str)
        self.assertGreater(len(report["content"]), 0)

    def test_local_tool_use_never_exposes_write_tools(self):
        """Directly verifies that write_file/delete_file/rename_file are
        never shown to the local model — with real mcp-tools and real
        Ollama."""
        from assistant.conversation import _mcp_tools_to_ollama_tools, LOCAL_SAFE_TOOL_NAMES

        with MCPClient(cwd="../mcp-tools") as client:
            safe_tools = [t for t in client.list_tools() if t["name"] in LOCAL_SAFE_TOOL_NAMES]
            ollama_tools = _mcp_tools_to_ollama_tools(safe_tools)
        tool_names = {t["function"]["name"] for t in ollama_tools}
        self.assertNotIn("write_file", tool_names)
        self.assertNotIn("delete_file", tool_names)
        self.assertNotIn("rename_file", tool_names)
        self.assertIn("hardware_tier", tool_names)

    def test_local_prompt_that_needs_tool_gets_real_correct_answer(self):
        """The exact scenario that failed first in real testing in Phase 4: a
        short hardware question now produces the right answer (thanks to the
        schema filter fix) — see assistant/README.md. It is retried a limited
        number of times because of the small model's known variability (see
        _run_cli_until).

        Thanks to the 'might this need tools?' signal added to the router,
        this prompt now falls through to the cloud by default under the
        `balanced` preference (see router/tests/test_integration.py
        test_short_tool_prompt_decide_only_routes_cloud_on_this_low_tier_machine)
        — local is forced here with --prefer cost, to verify that local
        tool-use works correctly (since it is still the path used when privacy
        or cost is preferred)."""
        prompt = "How many CPU cores does this machine have? Use the tool to find out, answer briefly."
        report = self._run_cli_until(
            prompt,
            predicate=lambda r: r.get("status") == "ok" and "6" in r.get("content", ""),
            extra_args=["--prefer", "cost"],
        )
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["route"], "local")
        self.assertIn("6", report["content"])

    def test_history_persists_across_separate_processes_via_history_file(self):
        """With --history-file the conversation history is persistent ACROSS
        SEPARATE processes — every run remembers the earlier turns, whether
        REPL or --prompt. Verified with real Ollama generation over the local
        path (no credentials needed). The second turn's content quality
        (remembering the name) retries a limited number of times because of the
        small model's known variability — before each attempt the history file
        is reset to its state after the first turn (see _run_cli_until,
        assistant/README.md)."""
        fd, history_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(history_path)  # let the assistant create it itself
        try:
            first = self._run_cli(
                "My name is Ahmet, don't forget it.", ["--history-file", history_path]
            )
            self.assertEqual(first["route"], "local")
            self.assertTrue(os.path.exists(history_path))
            with open(history_path, encoding="utf-8") as f:
                history_after_first_turn = json.load(f)
            self.assertEqual(
                history_after_first_turn[0],
                {"role": "user", "content": "My name is Ahmet, don't forget it."},
            )

            second = None
            for _ in range(3):
                with open(history_path, "w", encoding="utf-8") as f:
                    json.dump(history_after_first_turn, f, ensure_ascii=False)
                second = self._run_cli(
                    "What was my name? Just say the name.", ["--history-file", history_path]
                )
                if "Ahmet" in second["content"]:
                    break

            self.assertIn("Ahmet", second["content"])
            self.assertEqual(len(second["history"]), 4)
        finally:
            if os.path.exists(history_path):
                os.remove(history_path)

    @unittest.skipUnless(
        HAS_CLOUD_CREDENTIALS, "ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN is not set"
    )
    def test_complex_prompt_routes_cloud_and_uses_real_hardware_tool(self):
        long_prompt = (
            "How many CPU cores does this machine have, how much total RAM, and "
            "is there a discrete graphics card — please find all of this out "
            "using the real hardware detection tool and summarise it for me "
            "clearly as bullet points, never guess, rely only on the real data "
            "the tool returns, and keep it short."
        )
        report = self._run_cli(long_prompt)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["route"], "cloud")
        self.assertEqual(report["tool_calls"], [{"name": "hardware_tier", "input": {}}])
        self.assertIn("6", report["content"])  # the real core count
        self.assertIn("15", report["content"])  # the real RAM (~15.4 GB)

    @unittest.skipUnless(
        HAS_CLOUD_CREDENTIALS, "ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN is not set"
    )
    def test_mcp_client_and_run_cloud_turn_real_end_to_end(self):
        """Verifies the same flow by bypassing the CLI and using the internal
        API directly (a real mcp-tools subprocess + the real Claude API)."""
        from assistant.conversation import run_cloud_turn

        with MCPClient(cwd="../mcp-tools") as client:
            result = run_cloud_turn(
                "What is this machine's hardware tier? Really find out using the tool.",
                client,
            )
        self.assertEqual(result["route"], "cloud")
        self.assertTrue(any(tc["name"] == "hardware_tier" for tc in result["tool_calls"]))
        self.assertIn("low", result["content"].lower())


if __name__ == "__main__":
    unittest.main()
