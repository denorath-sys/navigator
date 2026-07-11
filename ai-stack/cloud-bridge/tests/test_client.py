import json
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from cloud_bridge.client import AnthropicClient, AnthropicError, DEFAULT_MODEL


def _fake_response(payload):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    return mock_resp


class TestAuthHeaders(unittest.TestCase):
    def setUp(self):
        self.client = AnthropicClient()

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True)
    def test_api_key_uses_x_api_key_header(self):
        headers = self.client._auth_headers()
        self.assertEqual(headers, {"x-api-key": "sk-ant-test"})

    @patch.dict("os.environ", {"ANTHROPIC_AUTH_TOKEN": "oauth-token"}, clear=True)
    def test_auth_token_uses_bearer_and_beta_header(self):
        headers = self.client._auth_headers()
        self.assertEqual(headers["Authorization"], "Bearer oauth-token")
        self.assertEqual(headers["anthropic-beta"], "oauth-2025-04-20")

    @patch.dict(
        "os.environ",
        {"ANTHROPIC_API_KEY": "sk-ant-test", "ANTHROPIC_AUTH_TOKEN": "oauth-token"},
        clear=True,
    )
    def test_api_key_takes_precedence_over_auth_token(self):
        headers = self.client._auth_headers()
        self.assertIn("x-api-key", headers)
        self.assertNotIn("Authorization", headers)

    @patch.dict("os.environ", {}, clear=True)
    def test_no_credentials_raises(self):
        with self.assertRaises(AnthropicError):
            self.client._auth_headers()


class TestIsAvailable(unittest.TestCase):
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True)
    def test_true_when_api_key_set(self):
        self.assertTrue(AnthropicClient().is_available())

    @patch.dict("os.environ", {}, clear=True)
    def test_false_when_no_credentials(self):
        self.assertFalse(AnthropicClient().is_available())

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True)
    @patch("cloud_bridge.client.urllib.request.urlopen")
    def test_is_available_makes_no_network_call(self, mock_urlopen):
        AnthropicClient().is_available()
        mock_urlopen.assert_not_called()


class TestGenerate(unittest.TestCase):
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True)
    @patch("cloud_bridge.client.urllib.request.urlopen")
    def test_generate_sends_correct_payload(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response(
            {"content": [{"type": "text", "text": "merhaba"}]}
        )
        client = AnthropicClient()
        result = client.generate("selam", max_tokens=100)

        self.assertEqual(result["content"][0]["text"], "merhaba")

        sent_request = mock_urlopen.call_args[0][0]
        sent_payload = json.loads(sent_request.data)
        self.assertEqual(sent_payload["model"], DEFAULT_MODEL)
        self.assertEqual(sent_payload["max_tokens"], 100)
        self.assertEqual(sent_payload["messages"][0]["content"], "selam")
        self.assertEqual(sent_request.get_header("X-api-key"), "sk-ant-test")
        self.assertEqual(
            sent_request.get_header("Anthropic-version"), "2023-06-01"
        )

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True)
    @patch("cloud_bridge.client.urllib.request.urlopen")
    def test_generate_includes_system_when_given(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({"content": []})
        AnthropicClient().generate("selam", system="Sen yardımcı bir asistansın.")
        sent_request = mock_urlopen.call_args[0][0]
        sent_payload = json.loads(sent_request.data)
        self.assertEqual(sent_payload["system"], "Sen yardımcı bir asistansın.")

    @patch.dict("os.environ", {}, clear=True)
    def test_generate_raises_without_credentials(self):
        with self.assertRaises(AnthropicError):
            AnthropicClient().generate("selam")

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True)
    @patch("cloud_bridge.client.urllib.request.urlopen")
    def test_generate_raises_anthropic_error_on_network_failure(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        with self.assertRaises(AnthropicError):
            AnthropicClient().generate("selam")


if __name__ == "__main__":
    unittest.main()
