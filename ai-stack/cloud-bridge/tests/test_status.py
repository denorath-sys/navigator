import unittest

from cloud_bridge.status import build_status_report


class FakeClient:
    def __init__(self, available):
        self._available = available

    def is_available(self):
        return self._available


class TestBuildStatusReport(unittest.TestCase):
    def test_credentials_configured_true(self):
        report = build_status_report(client=FakeClient(available=True))
        self.assertTrue(report["credentials_configured"])
        self.assertEqual(report["provider"], "anthropic")
        self.assertEqual(report["default_model"], "claude-opus-4-8")

    def test_credentials_configured_false(self):
        report = build_status_report(client=FakeClient(available=False))
        self.assertFalse(report["credentials_configured"])


if __name__ == "__main__":
    unittest.main()
