"""MCP JSON-RPC 2.0 dispatch mantığı — I/O'dan bağımsız, doğrudan test edilebilir."""

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "navigator-mcp-tools"
SERVER_VERSION = "0.1.0"


class MCPServer:
    def __init__(self):
        self._tools: dict[str, dict] = {}

    def register_tool(self, name: str, description: str, input_schema: dict, handler) -> None:
        self._tools[name] = {
            "description": description,
            "input_schema": input_schema,
            "handler": handler,
        }

    def handle_message(self, message: dict) -> dict | None:
        """Bir JSON-RPC isteğini işler. Notification'lar (id'siz mesajlar) için None döner."""
        method = message.get("method")
        msg_id = message.get("id")
        params = message.get("params", {}) or {}
        is_notification = "id" not in message

        if method is None:
            return None

        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "tools/list":
                result = self._handle_tools_list(params)
            elif method == "tools/call":
                result = self._handle_tools_call(params)
            elif method == "notifications/initialized":
                return None
            else:
                if is_notification:
                    return None
                return self._error_response(msg_id, -32601, f"Bilinmeyen metod: {method}")
        except Exception as e:
            if is_notification:
                return None
            return self._error_response(msg_id, -32603, str(e))

        if is_notification:
            return None
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def _handle_initialize(self, params: dict) -> dict:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }

    def _handle_tools_list(self, params: dict) -> dict:
        return {
            "tools": [
                {
                    "name": name,
                    "description": tool["description"],
                    "inputSchema": tool["input_schema"],
                }
                for name, tool in self._tools.items()
            ]
        }

    def _handle_tools_call(self, params: dict) -> dict:
        name = params.get("name")
        arguments = params.get("arguments", {}) or {}

        if name not in self._tools:
            return {
                "content": [{"type": "text", "text": f"Bilinmeyen araç: {name}"}],
                "isError": True,
            }

        try:
            text_result = self._tools[name]["handler"](**arguments)
            return {"content": [{"type": "text", "text": text_result}], "isError": False}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"Araç hatası: {e}"}], "isError": True}

    @staticmethod
    def _error_response(msg_id, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}
