"""MCP HTTP+SSE transport (the 2024-11-05 specification) — stdlib-only.

The classic two-endpoint model:
  - GET /sse: opens an SSE stream, generates a session_id, announces the URI
    the client should POST to via a first 'endpoint' event, and then streams
    the responses queued for that session as 'message' events.
  - POST /messages?session_id=<id>: handles the JSON-RPC request with the same
    MCPServer.handle_message() as stdio and adds the response to that
    session's queue; over HTTP it returns only 202 Accepted — the response
    itself arrives asynchronously over the SSE stream.

Both endpoints require Bearer token authentication (see auth.py) — a missing
or wrong `Authorization: Bearer <token>` gives a 401.

Note: this is not MCP's newer "Streamable HTTP" transport but the original
HTTP+SSE transport from the 2024-11-05 specification — consistent with the
protocolVersion advertised in server.py.
"""
import json
import queue
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .auth import extract_bearer_token, generate_token, tokens_match

SSE_PATH = "/sse"
MESSAGES_PATH = "/messages"
HEARTBEAT_INTERVAL = 15.0


class SSESessionRegistry:
    """Keeps the session_id -> response queue mapping thread-safe."""

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


def _make_handler(mcp_server, registry: SSESessionRegistry, token: str):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format, *args):
            pass  # silent, so as not to pollute stdout/stderr

        def _authenticated(self) -> bool:
            provided = extract_bearer_token(self.headers.get("Authorization"))
            if not tokens_match(provided, token):
                self._json_response(
                    401, {"error": "unauthorized"}, extra_headers={"WWW-Authenticate": "Bearer"}
                )
                return False
            return True

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path != SSE_PATH:
                self.send_response(404)
                self.end_headers()
                return
            if not self._authenticated():
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
                    if message is None:  # shutdown signal
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
            if not self._authenticated():
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

        def _json_response(self, status: int, payload: dict, extra_headers: dict | None = None) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for key, value in (extra_headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

    return Handler


def run_http_server(
    mcp_server, host: str = "127.0.0.1", port: int = 8765, token: str | None = None
) -> None:
    """Start the HTTP+SSE server (blocks). If `token` is not given one is
    generated automatically and printed to stderr — running without
    authentication is never possible."""
    if token is None:
        token = generate_token()
        print(f"[mcp-tools] Authentication token generated automatically: {token}", file=sys.stderr)
        print(
            "[mcp-tools] Requests must include an 'Authorization: Bearer <token>' header "
            "(use --token or NAVIGATOR_MCP_HTTP_TOKEN for a fixed token).",
            file=sys.stderr,
        )

    registry = SSESessionRegistry()
    handler_cls = _make_handler(mcp_server, registry, token)
    httpd = ThreadingHTTPServer((host, port), handler_cls)
    httpd.daemon_threads = True
    httpd.serve_forever()
