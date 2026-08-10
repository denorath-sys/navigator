"""CLI: `python3 -m mcp_tools` (stdio) veya
`python3 -m mcp_tools --http [--host H] [--port N] [--token T]` (HTTP+SSE)."""
import argparse
import os
import sys

from .filesystem import register_filesystem_tools
from .http_transport import run_http_server
from .hyprland import register_hyprland_tools
from .protocol import read_message, write_message
from .server import MCPServer
from .tools import register_default_tools

TOKEN_ENV_VAR = "NAVIGATOR_MCP_HTTP_TOKEN"


def build_server() -> MCPServer:
    server = MCPServer()
    register_default_tools(server)
    register_filesystem_tools(server)
    register_hyprland_tools(server)
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
        description="Navigator OS mcp-tools — MCP server (default: stdio, optional: HTTP+SSE)."
    )
    parser.add_argument("--http", action="store_true", help="stdio yerine HTTP+SSE transport kullan")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP modunda dinlenecek adres")
    parser.add_argument("--port", type=int, default=8765, help="HTTP modunda dinlenecek port")
    parser.add_argument(
        "--token",
        default=None,
        help=(
            "Bearer token for HTTP+SSE (if not given, the "
            f"{TOKEN_ENV_VAR} environment variable is used; failing that one is generated automatically and printed to stderr)"
        ),
    )
    args = parser.parse_args()

    server = build_server()

    if args.http:
        token = args.token or os.environ.get(TOKEN_ENV_VAR)
        run_http_server(server, host=args.host, port=args.port, token=token)
    else:
        run_stdio(server)

    return 0


if __name__ == "__main__":
    sys.exit(main())
