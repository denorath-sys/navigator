"""MCP stdio transport: satır sonuyla ayrılmış JSON-RPC 2.0 mesajları.

MCP spesifikasyonu (https://modelcontextprotocol.io) stdio transport için
mesajların newline ile ayrılmış, içinde newline barındırmayan JSON
nesneleri olmasını gerektirir (LSP'nin Content-Length header'lı çerçeveleme
yöntemi KULLANILMAZ — MCP daha basit).
"""
import json
import sys


def read_message(stream=sys.stdin):
    line = stream.readline()
    if not line:
        return None  # EOF
    line = line.strip()
    if not line:
        return read_message(stream)  # boş satırları atla
    return json.loads(line)


def write_message(message: dict, stream=sys.stdout) -> None:
    stream.write(json.dumps(message, ensure_ascii=False) + "\n")
    stream.flush()
