import json
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from assistant.conversation import (
    AssistantError,
    _extract_text,
    _mcp_tools_to_claude_tools,
    decide_route,
    run_cloud_turn,
    run_local_turn,
    run_turn,
)


def _fake_run(stdout: str, returncode: int = 0):
    return MagicMock(stdout=stdout, returncode=returncode)


class TestMcpToolsToClaudeTools(unittest.TestCase):
    def test_translates_schema_fields(self):
        mcp_tools = [
            {"name": "hardware_tier", "description": "...", "inputSchema": {"type": "object"}},
        ]
        claude_tools = _mcp_tools_to_claude_tools(mcp_tools)
        self.assertEqual(
            claude_tools,
            [{"name": "hardware_tier", "description": "...", "input_schema": {"type": "object"}}],
        )


class TestExtractText(unittest.TestCase):
    def test_concatenates_text_blocks_only(self):
        blocks = [
            {"type": "text", "text": "merhaba "},
            {"type": "tool_use", "name": "x", "input": {}},
            {"type": "text", "text": "dünya"},
        ]
        self.assertEqual(_extract_text(blocks), "merhaba dünya")


class TestDecideRoute(unittest.TestCase):
    @patch("assistant.conversation.subprocess.run")
    def test_calls_router_with_decide_only(self, mock_run):
        mock_run.return_value = _fake_run(json.dumps({"route": "local", "hardware_tier": "low"}))
        result = decide_route("selam", preference="privacy", router_cwd="../router")
        self.assertEqual(result["route"], "local")
        args = mock_run.call_args[0][0]
        self.assertIn("--decide-only", args)
        self.assertIn("privacy", args)
        self.assertEqual(mock_run.call_args[1]["cwd"], "../router")


class TestRunLocalTurn(unittest.TestCase):
    @patch("assistant.conversation.subprocess.run")
    def test_returns_content_on_ok_status(self, mock_run):
        mock_run.return_value = _fake_run(json.dumps({"status": "ok", "content": "merhaba!"}))
        result = run_local_turn("selam")
        self.assertEqual(result, {"content": "merhaba!", "tool_calls": [], "route": "local"})

    @patch("assistant.conversation.subprocess.run")
    def test_raises_when_not_ok(self, mock_run):
        mock_run.return_value = _fake_run(
            json.dumps({"status": "unavailable", "reason": "ollama_not_running"})
        )
        with self.assertRaises(AssistantError):
            run_local_turn("selam")


class TestRunCloudTurn(unittest.TestCase):
    def _fake_mcp_client(self, tool_result_text="42"):
        client = MagicMock()
        client.list_tools.return_value = [
            {"name": "hardware_tier", "description": "...", "inputSchema": {"type": "object"}}
        ]
        client.call_tool.return_value = {
            "content": [{"type": "text", "text": tool_result_text}],
            "isError": False,
        }
        return client

    @patch("assistant.conversation._call_cloud_bridge_converse")
    def test_returns_text_immediately_when_no_tool_use(self, mock_converse):
        mock_converse.return_value = {
            "content": [{"type": "text", "text": "merhaba"}],
            "stop_reason": "end_turn",
        }
        client = self._fake_mcp_client()
        result = run_cloud_turn("selam", client)
        self.assertEqual(result["content"], "merhaba")
        self.assertEqual(result["tool_calls"], [])
        self.assertEqual(result["route"], "cloud")
        client.call_tool.assert_not_called()

    @patch("assistant.conversation._call_cloud_bridge_converse")
    def test_executes_tool_call_and_feeds_result_back(self, mock_converse):
        responses = [
            {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "hardware_tier",
                        "input": {},
                    }
                ],
                "stop_reason": "tool_use",
            },
            {
                "content": [{"type": "text", "text": "tier düşük"}],
                "stop_reason": "end_turn",
            },
        ]
        captured_payloads = []

        def fake_converse(payload, cwd="../cloud-bridge"):
            captured_payloads.append(json.loads(json.dumps(payload)))  # o anki durumun kopyası
            return responses.pop(0)

        mock_converse.side_effect = fake_converse
        client = self._fake_mcp_client(tool_result_text='{"tier": "low"}')
        result = run_cloud_turn("donanımım nedir?", client)

        self.assertEqual(result["content"], "tier düşük")
        self.assertEqual(result["tool_calls"], [{"name": "hardware_tier", "input": {}}])
        client.call_tool.assert_called_once_with("hardware_tier", {})

        second_call_messages = captured_payloads[1]["messages"]
        tool_result_message = second_call_messages[-1]
        self.assertEqual(tool_result_message["role"], "user")
        self.assertEqual(tool_result_message["content"][0]["tool_use_id"], "toolu_1")
        self.assertEqual(tool_result_message["content"][0]["content"], '{"tier": "low"}')
        self.assertFalse(tool_result_message["content"][0]["is_error"])

    @patch("assistant.conversation._call_cloud_bridge_converse")
    def test_tool_call_exception_is_reported_as_error_result(self, mock_converse):
        responses = [
            {
                "content": [
                    {"type": "tool_use", "id": "toolu_1", "name": "hardware_tier", "input": {}}
                ],
                "stop_reason": "tool_use",
            },
            {"content": [{"type": "text", "text": "tamam"}], "stop_reason": "end_turn"},
        ]
        captured_payloads = []

        def fake_converse(payload, cwd="../cloud-bridge"):
            captured_payloads.append(json.loads(json.dumps(payload)))
            return responses.pop(0)

        mock_converse.side_effect = fake_converse
        client = self._fake_mcp_client()
        client.call_tool.side_effect = RuntimeError("mcp-tools çöktü")

        run_cloud_turn("x", client)

        second_call_messages = captured_payloads[1]["messages"]
        tool_result = second_call_messages[-1]["content"][0]
        self.assertTrue(tool_result["is_error"])
        self.assertIn("mcp-tools çöktü", tool_result["content"])

    @patch("assistant.conversation._call_cloud_bridge_converse")
    def test_raises_on_unavailable(self, mock_converse):
        mock_converse.return_value = {"status": "unavailable", "reason": "credentials_not_configured"}
        with self.assertRaises(AssistantError):
            run_cloud_turn("x", self._fake_mcp_client())

    @patch("assistant.conversation._call_cloud_bridge_converse")
    def test_raises_on_error_status(self, mock_converse):
        mock_converse.return_value = {"status": "error", "error": "boom"}
        with self.assertRaises(AssistantError):
            run_cloud_turn("x", self._fake_mcp_client())

    @patch("assistant.conversation._call_cloud_bridge_converse")
    def test_raises_after_max_iterations_infinite_tool_use(self, mock_converse):
        mock_converse.return_value = {
            "content": [
                {"type": "tool_use", "id": "toolu_1", "name": "hardware_tier", "input": {}}
            ],
            "stop_reason": "tool_use",
        }
        client = self._fake_mcp_client()
        with self.assertRaises(AssistantError):
            run_cloud_turn("x", client, max_iterations=3)
        self.assertEqual(mock_converse.call_count, 3)


class TestRunTurn(unittest.TestCase):
    @patch("assistant.conversation.run_local_turn")
    @patch("assistant.conversation.run_cloud_turn")
    @patch("assistant.conversation.decide_route")
    def test_dispatches_to_local_and_merges_decision_fields(
        self, mock_decide, mock_cloud, mock_local
    ):
        mock_decide.return_value = {
            "route": "local",
            "hardware_tier": "high",
            "reasoning": "model hazır",
        }
        mock_local.return_value = {"content": "merhaba", "tool_calls": [], "route": "local"}

        result = run_turn("selam", MagicMock())

        mock_local.assert_called_once()
        mock_cloud.assert_not_called()
        self.assertEqual(result["hardware_tier"], "high")
        self.assertEqual(result["reasoning"], "model hazır")

    @patch("assistant.conversation.run_local_turn")
    @patch("assistant.conversation.run_cloud_turn")
    @patch("assistant.conversation.decide_route")
    def test_dispatches_to_cloud(self, mock_decide, mock_cloud, mock_local):
        mock_decide.return_value = {"route": "cloud", "hardware_tier": "low", "reasoning": "karmaşık"}
        mock_cloud.return_value = {"content": "ok", "tool_calls": [], "route": "cloud"}

        result = run_turn("uzun ve karmaşık bir istek", MagicMock())

        mock_cloud.assert_called_once()
        mock_local.assert_not_called()
        self.assertEqual(result["route"], "cloud")


if __name__ == "__main__":
    unittest.main()
