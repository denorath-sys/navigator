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
        fake_cloud_result = {"status": "unavailable", "reason": "credentials_not_configured"}
        report = route_request(
            long_prompt,
            preference="balanced",
            status=status,
            cloud_bridge_caller=lambda prompt, cwd=None: fake_cloud_result,
        )
        self.assertEqual(report["route"], "cloud")
        self.assertEqual(report["complexity"], "complex")
        self.assertEqual(report["cloud_bridge"], fake_cloud_result)

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

    def test_local_route_does_not_call_cloud_bridge(self):
        status = {"hardware_tier": "high", "model_ready": True}
        called = []
        report = route_request(
            "basit bir soru",
            status=status,
            cloud_bridge_caller=lambda prompt, cwd=None: called.append(prompt),
        )
        self.assertEqual(report["route"], "local")
        self.assertNotIn("cloud_bridge", report)
        self.assertEqual(called, [])

    def test_cloud_route_calls_cloud_bridge_with_prompt(self):
        status = {"hardware_tier": "minimal", "model_ready": False}
        captured = {}

        def fake_caller(prompt, cwd=None):
            captured["prompt"] = prompt
            captured["cwd"] = cwd
            return {"status": "ok", "content": "merhaba!"}

        report = route_request(
            "selam navigator",
            status=status,
            cloud_bridge_cwd="../cloud-bridge",
            cloud_bridge_caller=fake_caller,
        )
        self.assertEqual(report["route"], "cloud")
        self.assertEqual(captured["prompt"], "selam navigator")
        self.assertEqual(captured["cwd"], "../cloud-bridge")
        self.assertEqual(report["cloud_bridge"]["content"], "merhaba!")


if __name__ == "__main__":
    unittest.main()
