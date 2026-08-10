import unittest

from hardware_probe.cpu import parse_cpuinfo

SAMPLE = """processor\t: 0
vendor_id\t: GenuineIntel
model name\t: Intel(R) Core(TM) i5-8500 CPU @ 3.00GHz
physical id\t: 0
core id\t\t: 0
cpu cores\t: 6

processor\t: 1
vendor_id\t: GenuineIntel
model name\t: Intel(R) Core(TM) i5-8500 CPU @ 3.00GHz
physical id\t: 0
core id\t\t: 1
cpu cores\t: 6
"""


class TestParseCpuinfo(unittest.TestCase):
    def test_counts_and_model(self):
        result = parse_cpuinfo(SAMPLE)
        self.assertEqual(result["cores_logical"], 2)
        self.assertEqual(result["cores_physical"], 2)
        self.assertEqual(result["model"], "Intel(R) Core(TM) i5-8500 CPU @ 3.00GHz")

    def test_hyperthreading_does_not_inflate_physical_count(self):
        # Two "processor" entries sharing the same core id (SMT/HT) must
        # count as a single physical core.
        smt_sample = SAMPLE.replace("core id\t\t: 1", "core id\t\t: 0")
        result = parse_cpuinfo(smt_sample)
        self.assertEqual(result["cores_logical"], 2)
        self.assertEqual(result["cores_physical"], 1)

    def test_empty_input(self):
        result = parse_cpuinfo("")
        self.assertEqual(result["cores_logical"], 0)
        self.assertEqual(result["cores_physical"], 0)
        self.assertEqual(result["model"], "unknown")

    def test_missing_physical_id_falls_back_to_logical_count(self):
        no_topology = "processor\t: 0\nmodel name\t: Fake CPU\n"
        result = parse_cpuinfo(no_topology)
        self.assertEqual(result["cores_logical"], 1)
        self.assertEqual(result["cores_physical"], 1)


if __name__ == "__main__":
    unittest.main()
