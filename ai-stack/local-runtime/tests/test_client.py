import json
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from local_runtime.client import OllamaClient, OllamaError


def _fake_response(payload):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    return mock_resp


class TestOllamaClient(unittest.TestCase):
    def setUp(self):
        self.client = OllamaClient()

    @patch("local_runtime.client.urllib.request.urlopen")
    def test_is_available_true(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({"version": "0.1.0"})
        self.assertTrue(self.client.is_available())

    @patch("local_runtime.client.urllib.request.urlopen")
    def test_is_available_false_on_connection_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        self.assertFalse(self.client.is_available())

    @patch("local_runtime.client.urllib.request.urlopen")
    def test_list_models(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response(
            {"models": [{"name": "llama3.2:3b"}, {"name": "llama3.1:8b"}]}
        )
        self.assertEqual(self.client.list_models(), ["llama3.2:3b", "llama3.1:8b"])

    @patch("local_runtime.client.urllib.request.urlopen")
    def test_list_models_raises_ollama_error_on_failure(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        with self.assertRaises(OllamaError):
            self.client.list_models()

    @patch("local_runtime.client.urllib.request.urlopen")
    def test_generate_sends_correct_payload(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({"response": "hello"})
        result = self.client.generate("llama3.2:3b", "hi")
        self.assertEqual(result["response"], "hello")

        sent_request = mock_urlopen.call_args[0][0]
        sent_payload = json.loads(sent_request.data)
        self.assertEqual(sent_payload["model"], "llama3.2:3b")
        self.assertEqual(sent_payload["prompt"], "hi")

    @patch("local_runtime.client.urllib.request.urlopen")
    def test_generate_raises_ollama_error_on_failure(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        with self.assertRaises(OllamaError):
            self.client.generate("llama3.2:3b", "hi")

    @patch("local_runtime.client.urllib.request.urlopen")
    def test_chat_sends_messages_and_returns_response(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response(
            {"message": {"role": "assistant", "content": "hello"}}
        )
        messages = [{"role": "user", "content": "hi"}]
        result = self.client.chat("llama3.2:3b", messages)
        self.assertEqual(result["message"]["content"], "hello")

        sent_payload = json.loads(mock_urlopen.call_args[0][0].data)
        self.assertEqual(sent_payload["model"], "llama3.2:3b")
        self.assertEqual(sent_payload["messages"], messages)
        self.assertNotIn("tools", sent_payload)

    @patch("local_runtime.client.urllib.request.urlopen")
    def test_chat_includes_tools_when_given(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({"message": {"role": "assistant", "content": ""}})
        tools = [{"type": "function", "function": {"name": "hardware_tier"}}]
        self.client.chat("llama3.2:3b", [{"role": "user", "content": "x"}], tools=tools)
        sent_payload = json.loads(mock_urlopen.call_args[0][0].data)
        self.assertEqual(sent_payload["tools"], tools)

    @patch("local_runtime.client.urllib.request.urlopen")
    def test_chat_raises_ollama_error_on_failure(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        with self.assertRaises(OllamaError):
            self.client.chat("llama3.2:3b", [{"role": "user", "content": "x"}])


if __name__ == "__main__":
    unittest.main()
