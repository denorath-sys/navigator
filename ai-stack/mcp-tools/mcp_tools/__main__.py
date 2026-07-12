"""CLI: `python3 -m mcp_tools` (stdio) veya
`python3 -m mcp_tools --http [--host H] [--port N]` (HTTP+SSE)."""
import argparse
import sys

from .filesystem import register_filesystem_tools
from .http_transport import run_http_server
from .protocol import read_message, write_message
from .server import MCPServer
from .tools import register_default_tools


def build_server() -> MCPServer:
    server = MCPServer()
    register_default_tools(server)
    register_filesystem_tools(server)
    return server


def run_stdio(server: MCPServer) -> None:
    while True:
        message = read_message()
        if message is None:
            break
        response = server.handle_message(message)
        if response is not None:
            write_message(response)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Navigator OS mcp-tools — MCP sunucusu (varsayılan: stdio, isteğe bağlı: HTTP+SSE)."
    )
    parser.add_argument("--http", action="store_true", help="stdio yerine HTTP+SSE transport kullan")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP modunda dinlenecek adres")
    parser.add_argument("--port", type=int, default=8765, help="HTTP modunda dinlenecek port")
    args = parser.parse_args()

    server = build_server()

    if args.http:
        run_http_server(server, host=args.host, port=args.port)
    else:
        run_stdio(server)

    return 0


if __name__ == "__main__":
    sys.exit(main())
