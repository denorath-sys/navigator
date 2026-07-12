import json
import os
import socket
import subprocess
import threading
import time
import unittest
import urllib.error
import urllib.request


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestHTTPTransportIntegration(unittest.TestCase):
    """Gerçek HTTP+SSE transport'una karşı uçtan uca çalışır — gerçek
    subprocess, gerçek TCP soketleri (mock yok)."""

    def setUp(self):
        self.port = _find_free_port()
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.proc = subprocess.Popen(
            ["python3", "-m", "mcp_tools", "--http", "--port", str(self.port)],
            cwd=here,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._wait_for_server()

    def tearDown(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self.proc.stdout.close()
        self.proc.stderr.close()

    def _wait_for_server(self, timeout: float = 5.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError("HTTP sunucusu zamanında ayağa kalkmadı")

    def _post(self, url: str, payload: dict) -> int:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(request, timeout=10) as resp:
            return resp.status

    def _read_endpoint_event(self, response) -> str:
        event_name = None
        while True:
            raw = response.readline()
            if not raw:
                raise RuntimeError("SSE akışı endpoint event'i gelmeden kapandı")
            line = raw.decode("utf-8").rstrip("\n")
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and event_name == "endpoint":
                return line.split(":", 1)[1].strip()

    def _collect_message_events(self, response, results: dict, expected_count: int) -> None:
        event_name = None
        while len(results) < expected_count:
            raw = response.readline()
            if not raw:
                break
            line = raw.decode("utf-8").rstrip("\n")
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and event_name == "message":
                parsed = json.loads(line.split(":", 1)[1].strip())
                if "id" in parsed:
                    results[parsed["id"]] = parsed

    def test_sse_endpoint_discovery_and_message_roundtrip(self):
        sse_response = urllib.request.urlopen(f"http://127.0.0.1:{self.port}/sse", timeout=10)
        try:
            endpoint_uri = self._read_endpoint_event(sse_response)
            self.assertTrue(endpoint_uri.startswith("/messages?session_id="))

            results: dict = {}
            reader = threading.Thread(
                target=self._collect_message_events, args=(sse_response, results, 3), daemon=True
            )
            reader.start()

            post_url = f"http://127.0.0.1:{self.port}{endpoint_uri}"
            self.assertEqual(
                self._post(post_url, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
                202,
            )
            self.assertEqual(
                self._post(post_url, {"jsonrpc": "2.0", "method": "notifications/initialized"}), 202
            )
            self.assertEqual(
                self._post(post_url, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
                202,
            )
            self.assertEqual(
                self._post(
                    post_url,
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {"name": "hardware_tier", "arguments": {}},
                    },
                ),
                202,
            )

            reader.join(timeout=10)

            self.assertIn(1, results)
            self.assertIn("serverInfo", results[1]["result"])

            self.assertIn(2, results)
            tool_names = {t["name"] for t in results[2]["result"]["tools"]}
            self.assertEqual(
                tool_names, {"hardware_tier", "route_request", "read_file", "list_directory"}
            )

            self.assertIn(3, results)
            self.assertFalse(results[3]["result"]["isError"])
        finally:
            sse_response.close()

    def test_post_without_session_id_returns_400(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post(
                f"http://127.0.0.1:{self.port}/messages",
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            )
        self.assertEqual(ctx.exception.code, 400)

    def test_post_with_unknown_session_id_returns_400(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post(
                f"http://127.0.0.1:{self.port}/messages?session_id=hicbir-zaman-olusturulmadi",
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            )
        self.assertEqual(ctx.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
