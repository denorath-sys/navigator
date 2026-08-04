import unittest
from pathlib import Path

from cloud_bridge.config import SOURCE_ENVIRONMENT, SOURCE_FILE, CredentialResolution
from cloud_bridge.status import build_status_report

CONFIG_PATH = Path("/var/home/navtest/.config/navigator/env")


class FakeClient:
    def __init__(self, resolution):
        self._resolution = resolution

    def resolve_credentials(self):
        return self._resolution


def _resolution(values=None, source=None, problem=None):
    return CredentialResolution(values or {}, source, CONFIG_PATH, problem)


class TestBuildStatusReport(unittest.TestCase):
    def test_credentials_configured_true(self):
        report = build_status_report(
            client=FakeClient(_resolution({"ANTHROPIC_API_KEY": "sk"}, SOURCE_ENVIRONMENT))
        )
        self.assertTrue(report["credentials_configured"])
        self.assertEqual(report["credentials_source"], "environment")
        self.assertEqual(report["provider"], "anthropic")
        self.assertEqual(report["default_model"], "claude-opus-4-8")

    def test_credentials_configured_false(self):
        report = build_status_report(client=FakeClient(_resolution()))
        self.assertFalse(report["credentials_configured"])
        self.assertIsNone(report["credentials_source"])
        self.assertIsNone(report["credentials_file_problem"])

    def test_file_source_and_path_are_reported(self):
        report = build_status_report(
            client=FakeClient(_resolution({"ANTHROPIC_API_KEY": "sk"}, SOURCE_FILE))
        )
        self.assertEqual(report["credentials_source"], "file")
        self.assertEqual(report["credentials_file"], str(CONFIG_PATH))

    def test_file_problem_is_reported(self):
        report = build_status_report(
            client=FakeClient(_resolution(problem="insecure_permissions"))
        )
        self.assertFalse(report["credentials_configured"])
        self.assertEqual(report["credentials_file_problem"], "insecure_permissions")

    def test_secret_value_never_appears_in_report(self):
        """Rapor kimlik bilgisinin KENDİSİNİ asla taşımamalı — bu çıktı
        log'lanabiliyor (router zinciri, CI adımları)."""
        report = build_status_report(
            client=FakeClient(_resolution({"ANTHROPIC_API_KEY": "sk-ant-gizli"}, SOURCE_FILE))
        )
        self.assertNotIn("sk-ant-gizli", repr(report))


if __name__ == "__main__":
    unittest.main()
