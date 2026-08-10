"""MCP stdio transport: newline-delimited JSON-RPC 2.0 messages.

For the stdio transport, the MCP specification
(https://modelcontextprotocol.io) requires messages to be newline-delimited
JSON objects containing no embedded newline (LSP's Content-Length header
framing is NOT USED — MCP is simpler).
"""
import json
import sys


def read_message(stream=sys.stdin):
    line = stream.readline()
    if not line:
        return None  # EOF
    line = line.strip()
    if not line:
        return read_message(stream)  # skip blank lines
    return json.loads(line)


def write_message(message: dict, stream=sys.stdout) -> None:
    stream.write(json.dumps(message, ensure_ascii=False) + "\n")
    stream.flush()
