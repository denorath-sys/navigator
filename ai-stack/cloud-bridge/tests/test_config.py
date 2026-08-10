import os
import tempfile
import unittest
from pathlib import Path

from cloud_bridge.config import (
    PROBLEM_INSECURE,
    PROBLEM_UNREADABLE,
    SOURCE_ENVIRONMENT,
    SOURCE_FILE,
    config_path,
    parse_env_text,
    resolve_credentials,
)


class TestConfigPath(unittest.TestCase):
    def test_defaults_to_home_config(self):
        path = config_path({"HOME": "/var/home/navtest"})
        self.assertEqual(path, Path("/var/home/navtest/.config/navigator/env"))

    def test_xdg_config_home_overrides(self):
        path = config_path({"HOME": "/var/home/navtest", "XDG_CONFIG_HOME": "/tmp/xdg"})
        self.assertEqual(path, Path("/tmp/xdg/navigator/env"))

    def test_relative_xdg_config_home_is_ignored(self):
        """XDG spec: a non-absolute XDG_CONFIG_HOME is ignored."""
        path = config_path({"HOME": "/var/home/navtest", "XDG_CONFIG_HOME": "relative/dir"})
        self.assertEqual(path, Path("/var/home/navtest/.config/navigator/env"))

    def test_empty_xdg_config_home_is_ignored(self):
        path = config_path({"HOME": "/var/home/navtest", "XDG_CONFIG_HOME": ""})
        self.assertEqual(path, Path("/var/home/navtest/.config/navigator/env"))


class TestParseEnvText(unittest.TestCase):
    def test_basic_key_value(self):
        values, problem = parse_env_text("ANTHROPIC_API_KEY=sk-ant-1\n")
        self.assertEqual(values, {"ANTHROPIC_API_KEY": "sk-ant-1"})
        self.assertIsNone(problem)

    def test_export_prefix_and_comments_and_blank_lines(self):
        text = (
            "# Navigator credentials\n"
            "\n"
            "export ANTHROPIC_API_KEY=sk-ant-2\n"
            "   # girintili yorum\n"
        )
        values, problem = parse_env_text(text)
        self.assertEqual(values, {"ANTHROPIC_API_KEY": "sk-ant-2"})
        self.assertIsNone(problem)

    def test_quotes_are_stripped(self):
        values, _ = parse_env_text('A="double"\nB=\'tek\'\n')
        self.assertEqual(values, {"A": "double", "B": "tek"})

    def test_spaces_around_equals_are_stripped(self):
        values, _ = parse_env_text("  ANTHROPIC_API_KEY = sk-ant-3  \n")
        self.assertEqual(values, {"ANTHROPIC_API_KEY": "sk-ant-3"})

    def test_value_may_contain_equals_and_hash(self):
        """NO inline comments: anything after `#` is part of the value
        (silently truncating an API key would produce an
        impossible-to-diagnose 401)."""
        values, problem = parse_env_text("K=a=b#c\n")
        self.assertEqual(values, {"K": "a=b#c"})
        self.assertIsNone(problem)

    def test_no_shell_expansion(self):
        values, _ = parse_env_text("K=$HOME/x\n")
        self.assertEqual(values, {"K": "$HOME/x"})

    def test_malformed_line_reports_line_number_but_keeps_rest(self):
        values, problem = parse_env_text("# comment\nmalformed line\nANTHROPIC_API_KEY=sk-ant-4\n")
        self.assertEqual(values, {"ANTHROPIC_API_KEY": "sk-ant-4"})
        self.assertEqual(problem, "malformed_line:2")

    def test_invalid_key_name_is_malformed(self):
        values, problem = parse_env_text("2BAD=x\n")
        self.assertEqual(values, {})
        self.assertEqual(problem, "malformed_line:1")

    def test_first_malformed_line_is_reported(self):
        _, problem = parse_env_text("bozuk1\nbozuk2\n")
        self.assertEqual(problem, "malformed_line:1")


class CredentialFileTestCase(unittest.TestCase):
    """Genuinely sets up `~/.config/navigator/env` under a temporary HOME."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)
        self.environ = {"HOME": str(self.home)}
        self.path = self.home / ".config" / "navigator" / "env"

    def write_config(self, text: str, mode: int = 0o600) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            os.chmod(self.path, 0o600)  # a previous subTest may have left 0o400
        self.path.write_text(text, encoding="utf-8")
        os.chmod(self.path, mode)
        return self.path


class TestResolveCredentials(CredentialFileTestCase):
    def test_missing_file_is_not_a_problem(self):
        res = resolve_credentials(environ=self.environ)
        self.assertEqual(res.values, {})
        self.assertIsNone(res.source)
        self.assertIsNone(res.problem)
        self.assertEqual(res.unavailable_reason, "credentials_not_configured")
        self.assertEqual(res.path, self.path)

    def test_reads_api_key_from_file(self):
        self.write_config("ANTHROPIC_API_KEY=sk-ant-file\n")
        res = resolve_credentials(environ=self.environ)
        self.assertEqual(res.values, {"ANTHROPIC_API_KEY": "sk-ant-file"})
        self.assertEqual(res.source, SOURCE_FILE)
        self.assertIsNone(res.problem)

    def test_reads_auth_token_from_file(self):
        self.write_config("export ANTHROPIC_AUTH_TOKEN=oauth-file\n")
        res = resolve_credentials(environ=self.environ)
        self.assertEqual(res.values, {"ANTHROPIC_AUTH_TOKEN": "oauth-file"})

    def test_environment_wins_and_file_is_not_read(self):
        """With an environment variable present the file is NEVER opened — so
        even a world-readable file produces no error."""
        self.write_config("ANTHROPIC_API_KEY=sk-ant-file\n", mode=0o644)
        env = {**self.environ, "ANTHROPIC_API_KEY": "sk-ant-env"}
        res = resolve_credentials(environ=env)
        self.assertEqual(res.values, {"ANTHROPIC_API_KEY": "sk-ant-env"})
        self.assertEqual(res.source, SOURCE_ENVIRONMENT)
        self.assertIsNone(res.problem)

    def test_empty_environment_value_falls_through_to_file(self):
        self.write_config("ANTHROPIC_API_KEY=sk-ant-file\n")
        env = {**self.environ, "ANTHROPIC_API_KEY": ""}
        res = resolve_credentials(environ=env)
        self.assertEqual(res.values, {"ANTHROPIC_API_KEY": "sk-ant-file"})
        self.assertEqual(res.source, SOURCE_FILE)

    def test_world_readable_file_is_refused(self):
        self.write_config("ANTHROPIC_API_KEY=sk-ant-file\n", mode=0o644)
        res = resolve_credentials(environ=self.environ)
        self.assertEqual(res.values, {})
        self.assertIsNone(res.source)
        self.assertEqual(res.problem, PROBLEM_INSECURE)
        self.assertEqual(res.unavailable_reason, "credentials_file_insecure")

    def test_group_readable_file_is_refused(self):
        self.write_config("ANTHROPIC_API_KEY=sk-ant-file\n", mode=0o640)
        res = resolve_credentials(environ=self.environ)
        self.assertEqual(res.problem, PROBLEM_INSECURE)

    def test_owner_only_read_write_is_accepted(self):
        for mode in (0o600, 0o400, 0o700):
            with self.subTest(mode=oct(mode)):
                self.write_config("ANTHROPIC_API_KEY=sk-ant-file\n", mode=mode)
                res = resolve_credentials(environ=self.environ)
                self.assertEqual(res.source, SOURCE_FILE, f"mode {oct(mode)} reddedildi")

    def test_undecodable_file_is_unreadable_not_a_crash(self):
        self.write_config("")
        self.path.write_bytes(b"\xff\xfe not utf-8")
        os.chmod(self.path, 0o600)
        res = resolve_credentials(environ=self.environ)
        self.assertEqual(res.problem, PROBLEM_UNREADABLE)
        self.assertEqual(res.unavailable_reason, "credentials_file_unreadable")

    def test_file_without_credential_keys_is_not_configured(self):
        self.write_config("SOME_OTHER_KEY=x\n")
        res = resolve_credentials(environ=self.environ)
        self.assertEqual(res.values, {})
        self.assertIsNone(res.source)
        self.assertEqual(res.unavailable_reason, "credentials_not_configured")

    def test_malformed_only_reports_malformed_reason(self):
        self.write_config("ANTHROPIC_API_KEY sk-ant-file\n")
        res = resolve_credentials(environ=self.environ)
        self.assertEqual(res.values, {})
        self.assertEqual(res.unavailable_reason, "credentials_file_malformed")

    def test_malformed_line_does_not_hide_a_valid_key(self):
        self.write_config("bozuk\nANTHROPIC_API_KEY=sk-ant-file\n")
        res = resolve_credentials(environ=self.environ)
        self.assertEqual(res.values, {"ANTHROPIC_API_KEY": "sk-ant-file"})
        self.assertEqual(res.source, SOURCE_FILE)
        self.assertEqual(res.problem, "malformed_line:1")

    def test_explicit_path_overrides_environment_lookup(self):
        other = self.home / "elsewhere"
        other.write_text("ANTHROPIC_API_KEY=sk-ant-elsewhere\n", encoding="utf-8")
        os.chmod(other, 0o600)
        res = resolve_credentials(environ=self.environ, path=other)
        self.assertEqual(res.values, {"ANTHROPIC_API_KEY": "sk-ant-elsewhere"})
        self.assertEqual(res.path, other)


if __name__ == "__main__":
    unittest.main()
