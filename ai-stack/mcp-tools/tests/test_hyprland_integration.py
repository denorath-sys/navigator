import json
import os
import subprocess
import unittest


class TestHyprlandToolsIntegration(unittest.TestCase):
    """Verifies the Hyprland tools against a real stdio MCP server process.

    On this machine (a Debian development environment) Hyprland is NOT
    installed or running — so what is verified here is not "real window data
    comes back" but "with no Hyprland, the tool fails gracefully with a clear
    error (isError: true) rather than crashing" — the same pattern as
    verifying cloud-bridge's credential-less path. Verification with real
    window/workspace data was deferred to Phase 3."""

    def _send(self, proc, message):
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    def _recv(self, proc):
        return json.loads(proc.stdout.readline())

    def test_hyprland_tools_listed_and_fail_gracefully_without_compositor(self):
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
            self._recv(proc)

            self._send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            tool_names = {t["name"] for t in self._recv(proc)["result"]["tools"]}
            self.assertIn("list_windows", tool_names)
            self.assertIn("list_workspaces", tool_names)
            self.assertIn("active_window", tool_names)

            for tool_id, tool_name in ((3, "list_windows"), (4, "list_workspaces"), (5, "active_window")):
                self._send(
                    proc,
                    {
                        "jsonrpc": "2.0",
                        "id": tool_id,
                        "method": "tools/call",
                        "params": {"name": tool_name, "arguments": {}},
                    },
                )
                response = self._recv(proc)
                self.assertTrue(response["result"]["isError"])
                text = response["result"]["content"][0]["text"]
                self.assertIn("Tool error:", text)
        finally:
            proc.stdin.close()
            proc.terminate()
            proc.wait(timeout=5)
            proc.stdout.close()
            proc.stderr.close()


if __name__ == "__main__":
    unittest.main()
