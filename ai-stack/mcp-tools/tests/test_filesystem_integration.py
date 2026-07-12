import json
import os
import subprocess
import tempfile
import unittest


class TestFilesystemToolsIntegration(unittest.TestCase):
    """Gerçek stdio MCP sunucu sürecine karşı dosya sistemi araçlarını
    doğrular — path traversal engellemesi dahil (NAVIGATOR_MCP_FS_ROOT ile
    izole bir sandbox'a yönlendirilir, gerçek ev dizinine dokunulmaz)."""

    def _send(self, proc, message):
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    def _recv(self, proc):
        return json.loads(proc.stdout.readline())

    def test_read_file_list_directory_and_traversal_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "hello.txt"), "w") as f:
                f.write("merhaba navigator")
            os.makedirs(os.path.join(tmp, "subdir"))

            here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            env = dict(os.environ)
            env["NAVIGATOR_MCP_FS_ROOT"] = tmp
            proc = subprocess.Popen(
                ["python3", "-m", "mcp_tools"],
                cwd=here,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env,
            )
            try:
                self._send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
                self._recv(proc)

                self._send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
                tool_names = {t["name"] for t in self._recv(proc)["result"]["tools"]}
                self.assertIn("read_file", tool_names)
                self.assertIn("list_directory", tool_names)
                self.assertIn("write_file", tool_names)

                self._send(
                    proc,
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {"name": "read_file", "arguments": {"path": "hello.txt"}},
                    },
                )
                read_response = self._recv(proc)
                self.assertFalse(read_response["result"]["isError"])
                self.assertEqual(read_response["result"]["content"][0]["text"], "merhaba navigator")

                self._send(
                    proc,
                    {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "list_directory", "arguments": {}}},
                )
                list_response = self._recv(proc)
                self.assertFalse(list_response["result"]["isError"])
                entries = json.loads(list_response["result"]["content"][0]["text"])
                names = {e["name"] for e in entries}
                self.assertEqual(names, {"hello.txt", "subdir"})

                self._send(
                    proc,
                    {
                        "jsonrpc": "2.0",
                        "id": 5,
                        "method": "tools/call",
                        "params": {"name": "read_file", "arguments": {"path": "../../../../etc/passwd"}},
                    },
                )
                traversal_response = self._recv(proc)
                self.assertTrue(traversal_response["result"]["isError"])
                self.assertIn("dışına çıkıyor", traversal_response["result"]["content"][0]["text"])

                self._send(
                    proc,
                    {
                        "jsonrpc": "2.0",
                        "id": 6,
                        "method": "tools/call",
                        "params": {
                            "name": "write_file",
                            "arguments": {"path": "yeni.txt", "content": "navigator yazdı"},
                        },
                    },
                )
                write_response = self._recv(proc)
                self.assertFalse(write_response["result"]["isError"])
                self.assertTrue(os.path.isfile(os.path.join(tmp, "yeni.txt")))
                with open(os.path.join(tmp, "yeni.txt"), encoding="utf-8") as f:
                    self.assertEqual(f.read(), "navigator yazdı")

                self._send(
                    proc,
                    {
                        "jsonrpc": "2.0",
                        "id": 7,
                        "method": "tools/call",
                        "params": {
                            "name": "write_file",
                            "arguments": {"path": "yeni.txt", "content": "tekrar"},
                        },
                    },
                )
                overwrite_denied_response = self._recv(proc)
                self.assertTrue(overwrite_denied_response["result"]["isError"])

                self._send(
                    proc,
                    {
                        "jsonrpc": "2.0",
                        "id": 8,
                        "method": "tools/call",
                        "params": {
                            "name": "write_file",
                            "arguments": {"path": "yeni.txt", "content": "tekrar", "overwrite": True},
                        },
                    },
                )
                overwrite_allowed_response = self._recv(proc)
                self.assertFalse(overwrite_allowed_response["result"]["isError"])
                with open(os.path.join(tmp, "yeni.txt"), encoding="utf-8") as f:
                    self.assertEqual(f.read(), "tekrar")

                self._send(
                    proc,
                    {
                        "jsonrpc": "2.0",
                        "id": 9,
                        "method": "tools/call",
                        "params": {
                            "name": "write_file",
                            "arguments": {"path": "../../../../tmp/kotu.txt", "content": "x"},
                        },
                    },
                )
                write_traversal_response = self._recv(proc)
                self.assertTrue(write_traversal_response["result"]["isError"])
                self.assertIn("dışına çıkıyor", write_traversal_response["result"]["content"][0]["text"])
            finally:
                proc.stdin.close()
                proc.terminate()
                proc.wait(timeout=5)
                proc.stdout.close()
                proc.stderr.close()


if __name__ == "__main__":
    unittest.main()
