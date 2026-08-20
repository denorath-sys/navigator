"""Exercises for qemu-input.py, against a fake QMP server.

The script's failure paths were exercised this way when it was written, in a
local session that left nothing behind. They are committed now, because the
alternative way of finding out whether an event sequence is right is a
twenty-five minute boot test — and because the scroll support added later
depends on an ORDER (modifier down, wheel, modifier up) that no amount of
reading proves.
"""

import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "qemu-input.py")

_spec = importlib.util.spec_from_file_location("qemu_input", SCRIPT)
qemu_input = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qemu_input)


class FakeQMP(threading.Thread):
    """Speaks just enough QMP: a greeting, replies to everything, and keeps
    every input-send-event batch it was given."""

    def __init__(self, path, greeting=None, error_on=None):
        super().__init__(daemon=True)
        self.path = path
        self.greeting = greeting if greeting is not None else {"QMP": {"version": {}}}
        self.error_on = error_on
        self.batches = []
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(path)
        self._server.listen(1)

    def run(self):
        conn, _ = self._server.accept()
        with conn:
            conn.sendall((json.dumps(self.greeting) + "\n").encode())
            buf = b""
            while True:
                try:
                    chunk = conn.recv(4096)
                except OSError:
                    return
                if not chunk:
                    return
                buf += chunk
                while b"\n" in buf:
                    line, _, buf = buf.partition(b"\n")
                    if not line.strip():
                        continue
                    msg = json.loads(line)
                    command = msg.get("execute")
                    if command == "input-send-event":
                        self.batches.append(msg["arguments"]["events"])
                    if command == self.error_on:
                        reply = {"error": {"class": "GenericError", "desc": "no"}}
                    else:
                        reply = {"return": {}}
                    conn.sendall((json.dumps(reply) + "\n").encode())

    def close(self):
        self._server.close()
        self.join(timeout=2)


class Harness(unittest.TestCase):
    def start_server(self, **kwargs):
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, "qmp.sock")
        server = FakeQMP(path, **kwargs)
        server.start()
        self.addCleanup(server.close)
        self.addCleanup(shutil.rmtree, directory, True)
        return server, path

    def run_script(self, *args):
        return subprocess.run(
            [sys.executable, SCRIPT, *args], capture_output=True, text=True, timeout=30
        )

    @staticmethod
    def flatten(batches):
        return [event for batch in batches for event in batch]


class TestAbsoluteAxes(unittest.TestCase):
    def test_maps_the_ends_of_the_screen_to_the_ends_of_the_range(self):
        self.assertEqual(qemu_input._abs(0, 1280), 0)
        self.assertEqual(qemu_input._abs(1279, 1280), 32767)

    def test_middle_is_the_middle(self):
        self.assertAlmostEqual(qemu_input._abs(640, 1281), 32767 // 2, delta=2)

    def test_off_screen_is_refused(self):
        with self.assertRaises(ValueError):
            qemu_input._abs(1280, 1280)
        with self.assertRaises(ValueError):
            qemu_input._abs(-1, 1280)


class TestEventShapes(unittest.TestCase):
    def test_wheel_is_a_button_pressed_and_released(self):
        events = qemu_input.wheel_events("down")
        self.assertEqual([e["data"]["button"] for e in events], ["wheel-down"] * 2)
        self.assertEqual([e["data"]["down"] for e in events], [True, False])

    def test_unknown_direction_and_modifier_are_refused(self):
        with self.assertRaises(ValueError):
            qemu_input.wheel_events("sideways")
        with self.assertRaises(ValueError):
            qemu_input.modifier_qcode("hyper")

    def test_super_is_the_meta_key(self):
        self.assertEqual(qemu_input.modifier_qcode("super"), "meta_l")


class TestAgainstFakeQMP(Harness):
    def test_scroll_holds_the_modifier_around_the_wheel(self):
        """The order is the claim: a binding is matched against the modifier
        state at the moment the wheel arrives, so a wheel that lands before
        the key press or after the release is just a scroll."""
        server, path = self.start_server()
        result = self.run_script(
            path, "scroll", "1280", "800", "640", "400",
            "--direction", "down", "--modifier", "super",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        events = self.flatten(server.batches)
        kinds = [(e["type"], e["data"].get("down")) for e in events]
        # two abs axes, meta down, wheel down, wheel up, meta up
        self.assertEqual(
            kinds,
            [("abs", None), ("abs", None), ("key", True),
             ("btn", True), ("btn", False), ("key", False)],
        )
        keys = [e for e in events if e["type"] == "key"]
        self.assertTrue(all(k["data"]["key"]["data"] == "meta_l" for k in keys))
        self.assertIn("scrolled down with super held", result.stdout)

    def test_scroll_without_a_modifier_sends_no_key(self):
        server, path = self.start_server()
        result = self.run_script(path, "scroll", "1280", "800", "10", "10", "--direction", "up")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([e["type"] for e in self.flatten(server.batches)],
                         ["abs", "abs", "btn", "btn"])

    def test_click_still_works(self):
        server, path = self.start_server()
        result = self.run_script(path, "click", "1280", "800", "100", "200")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([e["type"] for e in self.flatten(server.batches)],
                         ["abs", "abs", "btn", "btn"])

    def test_key_holds_the_modifier_around_the_press(self):
        server, path = self.start_server()
        result = self.run_script(path, "key", "ret", "--modifier", "super")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        events = self.flatten(server.batches)
        self.assertEqual(
            [(e["data"]["key"]["data"], e["data"]["down"]) for e in events],
            [("meta_l", True), ("ret", True), ("ret", False), ("meta_l", False)],
        )
        self.assertIn("pressed ret with super held", result.stdout)

    def test_key_without_a_modifier(self):
        server, path = self.start_server()
        result = self.run_script(path, "key", "ret")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.flatten(server.batches)), 2)

    def test_key_needs_no_coordinates(self):
        """A key press has nothing to do with where the pointer is, and
        demanding a screen size for one would be cargo cult."""
        server, path = self.start_server()
        self.assertEqual(self.run_script(path, "key", "ret").returncode, 0)

    def test_missing_direction_is_refused_before_connecting(self):
        result = self.run_script("/nonexistent.sock", "scroll", "1280", "800", "1", "1")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--direction", result.stdout)

    def test_missing_socket(self):
        result = self.run_script("/nonexistent.sock", "move", "1280", "800", "1", "1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("could not talk to QMP", result.stdout)

    def test_socket_that_is_not_qmp(self):
        server, path = self.start_server(greeting={"hello": "not qmp"})
        result = self.run_script(path, "move", "1280", "800", "1", "1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a QMP socket", result.stdout)

    def test_qmp_error_is_reported(self):
        server, path = self.start_server(error_on="input-send-event")
        result = self.run_script(path, "move", "1280", "800", "1", "1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("sending input failed", result.stdout)

    def test_off_screen_coordinate_is_refused(self):
        server, path = self.start_server()
        result = self.run_script(path, "click", "1280", "800", "2063", "16")
        self.assertEqual(result.returncode, 1)
        self.assertIn("outside 0..1279", result.stdout)


if __name__ == "__main__":
    unittest.main()
