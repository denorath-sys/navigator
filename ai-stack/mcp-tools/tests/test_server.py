import unittest

from mcp_tools.server import MCPServer


class TestMCPServer(unittest.TestCase):
    def setUp(self):
        self.server = MCPServer()

    def test_initialize_returns_protocol_info(self):
        response = self.server.handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        self.assertEqual(response["id"], 1)
        self.assertIn("protocolVersion", response["result"])
        self.assertIn("serverInfo", response["result"])

    def test_notification_returns_none(self):
        response = self.server.handle_message(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}
        )
        self.assertIsNone(response)

    def test_unknown_method_returns_error(self):
        response = self.server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "nope"})
        self.assertEqual(response["error"]["code"], -32601)

    def test_unknown_notification_method_returns_none(self):
        response = self.server.handle_message({"jsonrpc": "2.0", "method": "nope"})
        self.assertIsNone(response)

    def test_tools_list_empty_initially(self):
        response = self.server.handle_message({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
        self.assertEqual(response["result"]["tools"], [])

    def test_tools_list_reflects_registered_tool(self):
        self.server.register_tool(
            "echo",
            "Echoes input",
            {"type": "object", "properties": {"text": {"type": "string"}}},
            lambda text: text,
        )
        response = self.server.handle_message({"jsonrpc": "2.0", "id": 4, "method": "tools/list"})
        names = [t["name"] for t in response["result"]["tools"]]
        self.assertEqual(names, ["echo"])

    def test_tools_call_success(self):
        self.server.register_tool(
            "echo", "Echoes input", {"type": "object"}, lambda text: f"echo: {text}"
        )
        response = self.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "echo", "arguments": {"text": "merhaba"}},
            }
        )
        self.assertFalse(response["result"]["isError"])
        self.assertEqual(response["result"]["content"][0]["text"], "echo: merhaba")

    def test_tools_call_unknown_tool_is_error(self):
        response = self.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {"name": "yok", "arguments": {}},
            }
        )
        self.assertTrue(response["result"]["isError"])

    def test_tools_call_handler_exception_is_error(self):
        def boom():
            raise RuntimeError("patladı")

        self.server.register_tool("boom", "Patlar", {"type": "object"}, boom)
        response = self.server.handle_message(
            {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "boom", "arguments": {}}}
        )
        self.assertTrue(response["result"]["isError"])
        self.assertIn("patladı", response["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
