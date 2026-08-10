import unittest
from unittest.mock import patch

from router.status import route_request

_NOOP_LOCAL_RESULT = {"status": "unavailable", "reason": "ollama_not_running"}
_NOOP_CLOUD_RESULT = {"status": "unavailable", "reason": "credentials_not_configured"}


def _noop_local_caller(prompt, cwd=None):
    return _NOOP_LOCAL_RESULT


def _noop_cloud_caller(prompt, cwd=None):
    return _NOOP_CLOUD_RESULT


class TestRouteRequest(unittest.TestCase):
    def test_uses_provided_status_without_subprocess(self):
        status = {"hardware_tier": "mid", "model_ready": True}
        report = route_request(
            "basit bir soru",
            preference="balanced",
            status=status,
            local_runtime_caller=_noop_local_caller,
        )
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
        report = route_request("hi", local_runtime_caller=_noop_local_caller)
        self.assertEqual(report["route"], "local")
        mock_get_status.assert_called_once()

    def test_prompt_preview_truncates_long_prompt(self):
        status = {"hardware_tier": "mid", "model_ready": True}
        long_prompt = "a" * 200
        report = route_request(
            long_prompt, status=status, local_runtime_caller=_noop_local_caller
        )
        self.assertEqual(len(report["prompt_preview"]), 80)

    def test_local_route_does_not_call_cloud_bridge(self):
        status = {"hardware_tier": "high", "model_ready": True}
        cloud_called = []
        report = route_request(
            "basit bir soru",
            status=status,
            cloud_bridge_caller=lambda prompt, cwd=None: cloud_called.append(prompt),
            local_runtime_caller=_noop_local_caller,
        )
        self.assertEqual(report["route"], "local")
        self.assertNotIn("cloud_bridge", report)
        self.assertEqual(cloud_called, [])
        self.assertEqual(report["local_runtime"], _NOOP_LOCAL_RESULT)

    def test_cloud_route_calls_cloud_bridge_with_prompt(self):
        status = {"hardware_tier": "minimal", "model_ready": False}
        captured = {}

        def fake_caller(prompt, cwd=None):
            captured["prompt"] = prompt
            captured["cwd"] = cwd
            return {"status": "ok", "content": "hello!"}

        report = route_request(
            "hi navigator",
            status=status,
            cloud_bridge_cwd="../cloud-bridge",
            cloud_bridge_caller=fake_caller,
        )
        self.assertEqual(report["route"], "cloud")
        self.assertEqual(captured["prompt"], "hi navigator")
        self.assertEqual(captured["cwd"], "../cloud-bridge")
        self.assertEqual(report["cloud_bridge"]["content"], "hello!")

    def test_cloud_route_does_not_call_local_runtime(self):
        status = {"hardware_tier": "minimal", "model_ready": False}
        local_called = []
        report = route_request(
            "hi navigator",
            status=status,
            cloud_bridge_caller=_noop_cloud_caller,
            local_runtime_caller=lambda prompt, cwd=None: local_called.append(prompt),
        )
        self.assertEqual(report["route"], "cloud")
        self.assertNotIn("local_runtime", report)
        self.assertEqual(local_called, [])

    def test_decide_only_returns_report_without_calling_either_caller(self):
        status = {"hardware_tier": "high", "model_ready": True}
        local_called = []
        cloud_called = []
        report = route_request(
            "hi navigator",
            status=status,
            decide_only=True,
            local_runtime_caller=lambda prompt, cwd=None: local_called.append(prompt),
            cloud_bridge_caller=lambda prompt, cwd=None: cloud_called.append(prompt),
        )
        self.assertEqual(report["route"], "local")
        self.assertNotIn("local_runtime", report)
        self.assertNotIn("cloud_bridge", report)
        self.assertEqual(local_called, [])
        self.assertEqual(cloud_called, [])

    def test_decide_only_with_cloud_route_still_skips_execution(self):
        status = {"hardware_tier": "minimal", "model_ready": False}
        cloud_called = []
        report = route_request(
            "hi navigator",
            status=status,
            decide_only=True,
            cloud_bridge_caller=lambda prompt, cwd=None: cloud_called.append(prompt),
        )
        self.assertEqual(report["route"], "cloud")
        self.assertNotIn("cloud_bridge", report)
        self.assertEqual(cloud_called, [])

    def test_local_route_calls_local_runtime_with_prompt(self):
        status = {"hardware_tier": "high", "model_ready": True}
        captured = {}

        def fake_caller(prompt, cwd=None):
            captured["prompt"] = prompt
            captured["cwd"] = cwd
            return {"status": "ok", "content": "hello!"}

        report = route_request(
            "hi navigator",
            status=status,
            local_runtime_cwd="../local-runtime",
            local_runtime_caller=fake_caller,
        )
        self.assertEqual(report["route"], "local")
        self.assertEqual(captured["prompt"], "hi navigator")
        self.assertEqual(captured["cwd"], "../local-runtime")
        self.assertEqual(report["local_runtime"]["content"], "hello!")


if __name__ == "__main__":
    unittest.main()
