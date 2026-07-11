import unittest

from hardware_probe.memory import parse_meminfo

SAMPLE = """MemTotal:       16195024 kB
MemFree:         2966544 kB
MemAvailable:    8905688 kB
"""


class TestParseMeminfo(unittest.TestCase):
    def test_total_gb(self):
        result = parse_meminfo(SAMPLE)
        self.assertEqual(result["total_kb"], 16195024)
        self.assertAlmostEqual(result["total_gb"], 15.4, places=1)

    def test_missing_field_raises(self):
        with self.assertRaises(ValueError):
            parse_meminfo("MemFree: 100 kB\n")


if __name__ == "__main__":
    unittest.main()
