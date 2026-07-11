import unittest
from unittest.mock import patch

from router.status import route_request


class TestRouteRequest(unittest.TestCase):
    def test_uses_provided_status_without_subprocess(self):
        status = {"hardware_tier": "mid", "model_ready": True}
        report = route_request("basit bir soru", preference="balanced", status=status)
        self.assertEqual(report["route"], "local")
        self.assertEqual(report["hardware_tier"], "mid")

    def test_complex_prompt_with_low_tier_routes_cloud(self):
        status = {"hardware_tier": "low", "model_ready": True}
        long_prompt = " ".join(["kelime"] * 50)
        report = route_request(long_prompt, preference="balanced", status=status)
        self.assertEqual(report["route"], "cloud")
        self.assertEqual(report["complexity"], "complex")

    @patch("router.status.get_local_runtime_status")
    def test_calls_get_local_runtime_status_when_no_status_given(self, mock_get_status):
        mock_get_status.return_value = {"hardware_tier": "high", "model_ready": True}
        report = route_request("selam")
        self.assertEqual(report["route"], "local")
        mock_get_status.assert_called_once()

    def test_prompt_preview_truncates_long_prompt(self):
        status = {"hardware_tier": "mid", "model_ready": True}
        long_prompt = "a" * 200
        report = route_request(long_prompt, status=status)
        self.assertEqual(len(report["prompt_preview"]), 80)


if __name__ == "__main__":
    unittest.main()
