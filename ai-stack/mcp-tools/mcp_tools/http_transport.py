"""MCP HTTP+SSE transport (2024-11-05 spesifikasyonu) — stdlib-only.

Klasik iki uç noktalı model:
  - GET /sse: SSE akışı açar, bir session_id üretir, ilk 'endpoint' event'i
    ile istemcinin POST edeceği URI'yi bildirir, sonra o session'a ait
    kuyruğa giren yanıtları 'message' event'i olarak akıtır.
  - POST /messages?session_id=<id>: JSON-RPC isteğini stdio ile aynı
    MCPServer.handle_message() ile işler, yanıtı ilgili session'ın
    kuyruğuna ekler; HTTP olarak sadece 202 Accepted döner — yanıtın
    kendisi SSE akışı üzerinden asenkron gelir.

Not: Bu, MCP'nin daha yeni "Streamable HTTP" transport'u değil, orijinal
2024-11-05 spesifikasyonundaki HTTP+SSE transport'u — server.py'daki
protocolVersion ile tutarlı.
"""
import json
import queue
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

SSE_PATH = "/sse"
MESSAGES_PATH = "/messages"
HEARTBEAT_INTERVAL = 15.0


class SSESessionRegistry:
    """session_id -> yanıt kuyruğu eşlemesini thread-safe tutar."""

    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: dict[str, "queue.Queue"] = {}

    def create(self) -> tuple[str, "queue.Queue"]:
        session_id = uuid.uuid4().hex
        q: "queue.Queue" = queue.Queue()
        with self._lock:
            self._sessions[session_id] = q
        return session_id, q

    def get(self, session_id: str):
        with self._lock:
            return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


def _make_handler(mcp_server, registry: SSESessionRegistry):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format, *args):
            pass  # stdout/stderr'i kirletmemek için sessiz

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path != SSE_PATH:
                self.send_response(404)
                self.end_headers()
                return

            session_id, q = registry.create()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()

            endpoint_uri = f"{MESSAGES_PATH}?session_id={session_id}"
            try:
                self._write_event("endpoint", endpoint_uri)
                while True:
                    try:
                        message = q.get(timeout=HEARTBEAT_INTERVAL)
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                        continue
                    if message is None:  # kapatma sinyali
                        break
                    self._write_event("message", json.dumps(message, ensure_ascii=False))
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                registry.remove(session_id)

        def _write_event(self, event: str, data: str) -> None:
            self.wfile.write(f"event: {event}\ndata: {data}\n\n".encode("utf-8"))
            self.wfile.flush()

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path != MESSAGES_PATH:
                self._json_response(404, {"error": "not found"})
                return

            session_id = (parse_qs(parsed.query).get("session_id") or [None])[0]
            q = registry.get(session_id) if session_id else None
            if q is None:
                self._json_response(400, {"error": "unknown or missing session_id"})
                return

            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                message = json.loads(body)
            except ValueError:
                self._json_response(400, {"error": "invalid JSON"})
                return

            response = mcp_server.handle_message(message)
            if response is not None:
                q.put(response)

            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _json_response(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def run_http_server(mcp_server, host: str = "127.0.0.1", port: int = 8765) -> None:
    registry = SSESessionRegistry()
    handler_cls = _make_handler(mcp_server, registry)
    httpd = ThreadingHTTPServer((host, port), handler_cls)
    httpd.daemon_threads = True
    httpd.serve_forever()
