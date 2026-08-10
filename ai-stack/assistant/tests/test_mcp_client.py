import json
import unittest
from unittest.mock import MagicMock, patch

from assistant.mcp_client import MCPClient, MCPClientError


def _line(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


class TestMCPClient(unittest.TestCase):
    @patch("assistant.mcp_client.subprocess.Popen")
    def _make_client(self, mock_popen, initialize_response=None, extra_responses=None):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        responses = [
            initialize_response
            or {"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "navigator-mcp-tools"}}}
        ]
        responses.extend(extra_responses or [])
        mock_proc.stdout.readline.side_effect = [_line(r) for r in responses]
        mock_popen.return_value = mock_proc
        client = MCPClient(cwd="../mcp-tools")
        return client, mock_proc

    def test_initialize_sends_notification_after_response(self):
        client, mock_proc = self._make_client()
        written = [call.args[0] for call in mock_proc.stdin.write.call_args_list]
        self.assertIn('"method": "initialize"', written[0])
        self.assertIn('"notifications/initialized"', written[1])

    def test_list_tools_returns_tools_array(self):
        client, mock_proc = self._make_client(
            extra_responses=[
                {"jsonrpc": "2.0", "id": 2, "result": {"tools": [{"name": "hardware_tier"}]}}
            ]
        )
        tools = client.list_tools()
        self.assertEqual(tools, [{"name": "hardware_tier"}])

    def test_call_tool_sends_name_and_arguments(self):
        client, mock_proc = self._make_client(
            extra_responses=[
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {"content": [{"type": "text", "text": "ok"}], "isError": False},
                }
            ]
        )
        result = client.call_tool("read_file", {"path": "x.txt"})
        self.assertEqual(result["content"][0]["text"], "ok")
        sent = json.loads(mock_proc.stdin.write.call_args_list[-1].args[0])
        self.assertEqual(sent["method"], "tools/call")
        self.assertEqual(sent["params"], {"name": "read_file", "arguments": {"path": "x.txt"}})

    def test_error_response_raises(self):
        client, mock_proc = self._make_client(
            extra_responses=[
                {"jsonrpc": "2.0", "id": 2, "error": {"code": -32601, "message": "Bilinmeyen metod"}}
            ]
        )
        with self.assertRaises(MCPClientError):
            client.list_tools()

    def test_eof_raises_with_stderr(self):
        client, mock_proc = self._make_client()
        mock_proc.stdout.readline.side_effect = [""]  # EOF
        mock_proc.stderr.read.return_value = "traceback burada"
        with self.assertRaises(MCPClientError):
            client.list_tools()

    def test_context_manager_closes_on_exit(self):
        client, mock_proc = self._make_client()
        mock_proc.wait.return_value = None
        with client:
            pass
        mock_proc.stdin.close.assert_called_once()

    def test_close_is_idempotent_when_already_exited(self):
        client, mock_proc = self._make_client()
        mock_proc.poll.return_value = 0  # the process has already exited
        client.close()
        mock_proc.stdin.close.assert_not_called()


if __name__ == "__main__":
    unittest.main()
