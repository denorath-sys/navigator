import subprocess
import unittest
from unittest.mock import MagicMock, patch

from mcp_tools.hyprland import (
    HyprlandError,
    active_window,
    list_windows,
    list_workspaces,
)

ENV_WITH_HYPRLAND = {"HYPRLAND_INSTANCE_SIGNATURE": "abc123"}


class TestRunHyprctl(unittest.TestCase):
    """Bu makinede gerçek Hyprland çalışmadığından (Debian geliştirme
    ortamı) tüm senaryolar subprocess.run/shutil.which mock'lanarak test
    ediliyor — bkz. hyprland.py docstring'i, gerçek doğrulama Faz 3'e
    kaldı."""

    @patch("mcp_tools.hyprland.shutil.which", return_value=None)
    def test_hyprctl_not_found_raises(self, mock_which):
        with self.assertRaises(HyprlandError):
            list_windows()

    @patch.dict("os.environ", {}, clear=True)
    @patch("mcp_tools.hyprland.shutil.which", return_value="/usr/bin/hyprctl")
    def test_hyprland_not_running_raises(self, mock_which):
        with self.assertRaises(HyprlandError):
            list_windows()

    @patch.dict("os.environ", ENV_WITH_HYPRLAND, clear=True)
    @patch("mcp_tools.hyprland.shutil.which", return_value="/usr/bin/hyprctl")
    @patch("mcp_tools.hyprland.subprocess.run")
    def test_timeout_raises(self, mock_run, mock_which):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="hyprctl", timeout=5.0)
        with self.assertRaises(HyprlandError):
            list_windows()

    @patch.dict("os.environ", ENV_WITH_HYPRLAND, clear=True)
    @patch("mcp_tools.hyprland.shutil.which", return_value="/usr/bin/hyprctl")
    @patch("mcp_tools.hyprland.subprocess.run")
    def test_nonzero_returncode_raises(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="socket bulunamadı")
        with self.assertRaises(HyprlandError):
            list_windows()

    @patch.dict("os.environ", ENV_WITH_HYPRLAND, clear=True)
    @patch("mcp_tools.hyprland.shutil.which", return_value="/usr/bin/hyprctl")
    @patch("mcp_tools.hyprland.subprocess.run")
    def test_invalid_json_raises(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout="bu json değil", stderr="")
        with self.assertRaises(HyprlandError):
            list_windows()

    @patch.dict("os.environ", ENV_WITH_HYPRLAND, clear=True)
    @patch("mcp_tools.hyprland.shutil.which", return_value="/usr/bin/hyprctl")
    @patch("mcp_tools.hyprland.subprocess.run")
    def test_list_windows_parses_json_and_uses_clients_command(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(
            returncode=0, stdout='[{"address": "0x1", "class": "kitty", "title": "term"}]', stderr=""
        )
        result = list_windows()
        self.assertEqual(result, [{"address": "0x1", "class": "kitty", "title": "term"}])
        args = mock_run.call_args[0][0]
        self.assertEqual(args, ["hyprctl", "-j", "clients"])

    @patch.dict("os.environ", ENV_WITH_HYPRLAND, clear=True)
    @patch("mcp_tools.hyprland.shutil.which", return_value="/usr/bin/hyprctl")
    @patch("mcp_tools.hyprland.subprocess.run")
    def test_list_workspaces_uses_workspaces_command(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout='[{"id": 1, "name": "1"}]', stderr="")
        result = list_workspaces()
        self.assertEqual(result, [{"id": 1, "name": "1"}])
        args = mock_run.call_args[0][0]
        self.assertEqual(args, ["hyprctl", "-j", "workspaces"])

    @patch.dict("os.environ", ENV_WITH_HYPRLAND, clear=True)
    @patch("mcp_tools.hyprland.shutil.which", return_value="/usr/bin/hyprctl")
    @patch("mcp_tools.hyprland.subprocess.run")
    def test_active_window_uses_activewindow_command(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(
            returncode=0, stdout='{"address": "0x1", "class": "kitty"}', stderr=""
        )
        result = active_window()
        self.assertEqual(result, {"address": "0x1", "class": "kitty"})
        args = mock_run.call_args[0][0]
        self.assertEqual(args, ["hyprctl", "-j", "activewindow"])


if __name__ == "__main__":
    unittest.main()
