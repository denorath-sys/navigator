import unittest
from unittest.mock import patch

from local_runtime.status import build_status_report


class FakeClient:
    def __init__(self, available=True, models=None):
        self._available = available
        self._models = models or []

    def is_available(self):
        return self._available

    def list_models(self):
        return self._models


class TestBuildStatusReport(unittest.TestCase):
    @patch("local_runtime.status.get_hardware_tier")
    def test_mid_tier_model_not_installed(self, mock_get_tier):
        mock_get_tier.return_value = {"tier": "mid"}
        client = FakeClient(available=True, models=["llama3.2:3b"])
        report = build_status_report(ollama_client=client)
        self.assertEqual(report["hardware_tier"], "mid")
        self.assertEqual(report["recommended_model"]["model"], "llama3.1:8b")
        self.assertFalse(report["model_ready"])

    @patch("local_runtime.status.get_hardware_tier")
    def test_mid_tier_model_installed(self, mock_get_tier):
        mock_get_tier.return_value = {"tier": "mid"}
        client = FakeClient(available=True, models=["llama3.1:8b"])
        report = build_status_report(ollama_client=client)
        self.assertTrue(report["model_ready"])

    @patch("local_runtime.status.get_hardware_tier")
    def test_minimal_tier_has_no_recommendation(self, mock_get_tier):
        mock_get_tier.return_value = {"tier": "minimal"}
        client = FakeClient(available=False)
        report = build_status_report(ollama_client=client)
        self.assertIsNone(report["recommended_model"])
        self.assertFalse(report["model_ready"])

    @patch("local_runtime.status.get_hardware_tier")
    def test_ollama_unavailable_skips_list_models(self, mock_get_tier):
        mock_get_tier.return_value = {"tier": "low"}
        client = FakeClient(available=False)
        report = build_status_report(ollama_client=client)
        self.assertFalse(report["ollama_available"])
        self.assertEqual(report["installed_models"], [])


if __name__ == "__main__":
    unittest.main()
