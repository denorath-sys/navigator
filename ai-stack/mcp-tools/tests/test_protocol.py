import io
import unittest

from mcp_tools.protocol import read_message, write_message


class TestProtocol(unittest.TestCase):
    def test_write_then_read_roundtrip(self):
        out = io.StringIO()
        write_message({"jsonrpc": "2.0", "id": 1, "result": {}}, stream=out)
        out.seek(0)
        message = read_message(out)
        self.assertEqual(message, {"jsonrpc": "2.0", "id": 1, "result": {}})

    def test_read_returns_none_on_eof(self):
        empty = io.StringIO("")
        self.assertIsNone(read_message(empty))

    def test_read_skips_blank_lines(self):
        stream = io.StringIO('\n\n{"jsonrpc": "2.0", "id": 1, "method": "x"}\n')
        message = read_message(stream)
        self.assertEqual(message["method"], "x")

    def test_write_message_has_no_embedded_newline(self):
        out = io.StringIO()
        write_message({"jsonrpc": "2.0", "id": 1, "result": {"text": "a\\nb"}}, stream=out)
        line = out.getvalue()
        # there must be no newline other than the single line + trailing newline
        self.assertEqual(line.count("\n"), 1)


if __name__ == "__main__":
    unittest.main()
