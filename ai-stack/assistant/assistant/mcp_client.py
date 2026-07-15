"""mcp-tools'a karşı gerçek bir MCP istemcisi — stdio transport, stdlib-only.

`ai-stack/router`'ın diğer modülleri "tek seferlik" subprocess çağrılarıyla
(`python3 -m X --prompt ...`, süreç bitince JSON stdout okunur) kullanmasından
farklı olarak, burada MCP protokolünün gerektirdiği KALICI bir oturum var:
`initialize` bir kez yapılır, sonra aynı süreç üzerinden birden çok
`tools/call` isteği gönderilir (bkz. modelcontextprotocol.io).
"""
import json
import subprocess

MCP_TOOLS_CMD = ["python3", "-m", "mcp_tools"]


class MCPClientError(Exception):
    """mcp-tools sürecine bağlanılamadığında veya bir istek hata döndürdüğünde."""


class MCPClient:
    def __init__(self, cwd: str = "../mcp-tools"):
        self._proc = subprocess.Popen(
            MCP_TOOLS_CMD,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._next_id = 1
        self._initialize()

    def __enter__(self) -> "MCPClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _send(self, message: dict) -> None:
        self._proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()

    def _recv(self) -> dict:
        line = self._proc.stdout.readline()
        if not line:
            stderr = self._proc.stderr.read()
            raise MCPClientError(f"mcp-tools süreci beklenmedik şekilde kapandı: {stderr}")
        return json.loads(line)

    def _request(self, method: str, params: dict | None = None) -> dict:
        msg_id = self._next_id
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}})
        response = self._recv()
        if "error" in response:
            raise MCPClientError(f"mcp-tools hata döndü ({method}): {response['error']}")
        return response["result"]

    def _initialize(self) -> None:
        self._request("initialize")
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def list_tools(self) -> list[dict]:
        """`[{"name", "description", "inputSchema"}, ...]` döner."""
        return self._request("tools/list")["tools"]

    def call_tool(self, name: str, arguments: dict) -> dict:
        """`{"content": [{"type": "text", "text": ...}], "isError": bool}` döner."""
        return self._request("tools/call", {"name": name, "arguments": arguments})

    def close(self) -> None:
        if self._proc.poll() is not None:
            return
        self._proc.stdin.close()
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.terminate()
            self._proc.wait(timeout=5)
        self._proc.stdout.close()
        self._proc.stderr.close()
