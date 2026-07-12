"""CLI: `python3 -m mcp_tools` — stdio üzerinden MCP sunucusunu başlatır."""
import sys

from .filesystem import register_filesystem_tools
from .protocol import read_message, write_message
from .server import MCPServer
from .tools import register_default_tools


def main() -> int:
    server = MCPServer()
    register_default_tools(server)
    register_filesystem_tools(server)

    while True:
        message = read_message()
        if message is None:
            break
        response = server.handle_message(message)
        if response is not None:
            write_message(response)

    return 0


if __name__ == "__main__":
    sys.exit(main())
