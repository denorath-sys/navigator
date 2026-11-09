"""Tests for the CLI layer (`assistant/__main__.py`) that the shell panel
talks to: where the default history lives, how it is written, `--reset`, and
the structured error report the panel translates into a sentence.

The conversation itself is mocked here (it has its own tests in
test_conversation.py and real ones in test_integration.py); what is under test
is the contract between the CLI and its caller."""
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from assistant import __main__ as cli
from assistant.conversation import AssistantError


def _run_main(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(sys, "argv", ["assistant", *argv]), redirect_stdout(out), redirect_stderr(err):
        code = cli.main()
    return code, out.getvalue(), err.getvalue()


class TestDefaultHistoryPath(unittest.TestCase):
    def test_uses_absolute_xdg_state_home(self):
        self.assertEqual(
            cli.default_history_path({"XDG_STATE_HOME": "/x/state", "HOME": "/home/u"}),
            Path("/x/state/navigator/assistant-history.json"),
        )

    def test_falls_back_to_home_when_xdg_unset_empty_or_relative(self):
        expected = Path("/home/u/.local/state/navigator/assistant-history.json")
        for env in ({"HOME": "/home/u"}, {"XDG_STATE_HOME": "", "HOME": "/home/u"},
                    {"XDG_STATE_HOME": "relative/state", "HOME": "/home/u"}):
            with self.subTest(env=env):
                self.assertEqual(cli.default_history_path(env), expected)


class _TempHome(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        patcher = mock.patch.dict(os.environ, {"HOME": str(self.home)}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("XDG_STATE_HOME", None)
        self.addCleanup(self._tmp.cleanup)
        self.history_path = self.home / ".local/state/navigator/assistant-history.json"

    def _patch_turn(self, **kwargs):
        """Replace the MCP client and the turn itself; returns the run_turn mock."""
        client = mock.MagicMock()
        client.__enter__.return_value = client
        p1 = mock.patch.object(cli, "MCPClient", return_value=client)
        p2 = mock.patch.object(cli, "run_turn", **kwargs)
        p1.start()
        run_turn = p2.start()
        self.addCleanup(p1.stop)
        self.addCleanup(p2.stop)
        return run_turn


class TestDefaultHistory(_TempHome):
    def test_successful_turn_is_saved_private_and_reloaded(self):
        run_turn = self._patch_turn(
            side_effect=lambda prompt, client, history, **kw: {
                "content": "hi",
                "tool_calls": [],
                "route": "cloud",
                "history": history + [{"role": "user", "content": prompt},
                                      {"role": "assistant", "content": "hi"}],
            }
        )
        code, out, _ = _run_main(["--prompt", "first", "--default-history"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["status"], "ok")

        self.assertTrue(self.history_path.exists())
        self.assertEqual(stat.S_IMODE(self.history_path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.history_path.parent.stat().st_mode), 0o700)
        # No temporary file is left next to it.
        self.assertEqual(os.listdir(self.history_path.parent), [self.history_path.name])

        _run_main(["--prompt", "second", "--default-history"])
        self.assertEqual(run_turn.call_args.kwargs["history"][0]["content"], "first")
        self.assertEqual(len(json.loads(self.history_path.read_text())), 4)

    def test_failed_turn_does_not_touch_history(self):
        self._patch_turn(side_effect=AssistantError("x", reason="credentials_not_configured"))
        code, _, _ = _run_main(["--prompt", "q", "--default-history"])
        self.assertEqual(code, 1)
        self.assertFalse(self.history_path.exists())

    def test_history_file_and_default_history_are_mutually_exclusive(self):
        with self.assertRaises(SystemExit):
            _run_main(["--prompt", "q", "--default-history", "--history-file", "/tmp/x.json"])


class TestErrorReport(_TempHome):
    def _error(self, err: str) -> dict:
        self.assertNotEqual(err, "")
        return json.loads(err)

    def test_assistant_error_reason_is_its_own_field(self):
        """The panel matches on `reason`, never on the message text."""
        self._patch_turn(
            side_effect=AssistantError(
                "cloud-bridge unavailable: credentials_not_configured",
                reason="credentials_not_configured",
            )
        )
        code, out, err = _run_main(["--prompt", "q", "--default-history"])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        report = self._error(err)
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["reason"], "credentials_not_configured")

    def test_error_without_reason_has_no_reason_field(self):
        self._patch_turn(side_effect=AssistantError("loop"))
        _, _, err = _run_main(["--prompt", "q"])
        self.assertNotIn("reason", self._error(err))

    def test_subprocess_failure_is_reported_not_a_traceback(self):
        self._patch_turn(
            side_effect=subprocess.CalledProcessError(
                1, ["python3", "-m", "router"], stderr="Traceback ...\nValueError: boom\n"
            )
        )
        code, _, err = _run_main(["--prompt", "q"])
        self.assertEqual(code, 1)
        report = self._error(err)
        self.assertEqual(report["reason"], cli.REASON_SUBPROCESS_FAILED)
        self.assertIn("ValueError: boom", report["error"])

    def test_malformed_history_is_reported_and_reset_recovers(self):
        self.history_path.parent.mkdir(parents=True)
        for bad in ("{not json", '{"role": "user"}', '[{"no_role": 1}]'):
            with self.subTest(bad=bad):
                self.history_path.write_text(bad)
                run_turn = self._patch_turn(return_value={})
                code, _, err = _run_main(["--prompt", "q", "--default-history"])
                self.assertEqual(code, 1)
                self.assertEqual(self._error(err)["reason"], cli.REASON_HISTORY_MALFORMED)
                run_turn.assert_not_called()

        code, out, _ = _run_main(["--reset", "--default-history"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"schema_version": cli.SCHEMA_VERSION, "status": "ok", "reset": True})
        self.assertEqual(json.loads(self.history_path.read_text()), [])

    def test_reset_without_a_history_file_is_an_error(self):
        code, _, err = _run_main(["--reset"])
        self.assertEqual(code, 2)
        self.assertEqual(self._error(err)["status"], "error")


if __name__ == "__main__":
    unittest.main()
