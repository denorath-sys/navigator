import unittest

from hardware_probe.probe import run_probe


class TestRunProbeIntegration(unittest.TestCase):
    """Bu makinenin gerçek /proc ve /sys/class/drm'ine karşı çalışır."""

    def test_runs_without_crashing_on_real_system(self):
        report = run_probe()
        self.assertIn("schema_version", report)
        self.assertIn(report["tier"], ("minimal", "low", "mid", "high"))
        self.assertGreater(report["cpu"]["cores_logical"], 0)
        self.assertGreater(report["memory"]["total_gb"], 0)
        self.assertIsInstance(report["gpu"]["devices"], list)


if __name__ == "__main__":
    unittest.main()
