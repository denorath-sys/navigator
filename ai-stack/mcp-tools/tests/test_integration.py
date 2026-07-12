import json
import os
import subprocess
import unittest


class TestMCPToolsIntegration(unittest.TestCase):
    """Gerçek stdio MCP sunucu sürecine karşı uçtan uca protokol testi."""

    def _send(self, proc, message):
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    def _recv(self, proc):
        line = proc.stdout.readline()
        return json.loads(line)

    def test_initialize_tools_list_and_call(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        proc = subprocess.Popen(
            ["python3", "-m", "mcp_tools"],
            cwd=here,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        try:
            self._send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            init_response = self._recv(proc)
            self.assertEqual(init_response["id"], 1)
            self.assertIn("serverInfo", init_response["result"])

            self._send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

            self._send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            list_response = self._recv(proc)
            tool_names = {t["name"] for t in list_response["result"]["tools"]}
            self.assertEqual(
                tool_names,
                {
                    "hardware_tier",
                    "route_request",
                    "read_file",
                    "list_directory",
                    "write_file",
                    "delete_file",
                    "rename_file",
                    "list_windows",
                    "list_workspaces",
                    "active_window",
                },
            )

            self._send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "hardware_tier", "arguments": {}},
                },
            )
            call_response = self._recv(proc)
            self.assertFalse(call_response["result"]["isError"])
            tier_report = json.loads(call_response["result"]["content"][0]["text"])
            self.assertIn(tier_report["tier"], ("minimal", "low", "mid", "high"))
        finally:
            proc.stdin.close()
            proc.terminate()
            proc.wait(timeout=5)
            proc.stdout.close()
            proc.stderr.close()


if __name__ == "__main__":
    unittest.main()
