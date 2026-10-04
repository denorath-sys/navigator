"""Exercises for evdev-watch.py's decoding.

The script only earns its keep if what it prints can be trusted without a
second opinion, and the one way to check it against a real device is the boot
test it was written to shorten.
"""

import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "evdev-watch.py")

_spec = importlib.util.spec_from_file_location("evdev_watch", SCRIPT)
evdev_watch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(evdev_watch)


def event(etype, code, value):
    return evdev_watch.EVENT.pack(0, 0, etype, code, value)


class TestDecode(unittest.TestCase):
    def test_a_wheel_notch_down_is_rel_wheel_minus_one(self):
        buf = event(2, 8, -1) + event(0, 0, 0)
        self.assertEqual(evdev_watch.decode(buf), [(2, 8, -1)])

    def test_sync_events_are_left_out(self):
        self.assertEqual(evdev_watch.decode(event(0, 0, 0) * 3), [])

    def test_a_trailing_partial_event_is_ignored(self):
        buf = event(2, 8, 1) + b"\x00" * 5
        self.assertEqual(evdev_watch.decode(buf), [(2, 8, 1)])

    def test_an_event_is_twenty_four_bytes(self):
        """The layout this decoder assumes; a 32-bit guest would differ."""
        self.assertEqual(evdev_watch.EVENT.size, 24)


class TestSummarise(unittest.TestCase):
    def test_groups_by_kind_and_keeps_the_values(self):
        lines = evdev_watch.summarise([(2, 8, -1), (2, 8, 1), (1, 0x151, 0)])
        self.assertEqual(
            lines,
            ["REL_WHEEL x2 values=[-1, 1]", "BTN_GEAR_UP x1 values=[0]"],
        )

    def test_an_unknown_code_is_printed_rather_than_dropped(self):
        self.assertEqual(
            evdev_watch.summarise([(4, 4, 7)]), ["type=4 code=4 x1 values=[7]"]
        )

    def test_nothing_in_nothing_out(self):
        self.assertEqual(evdev_watch.summarise([]), [])


if __name__ == "__main__":
    unittest.main()
