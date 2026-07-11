import unittest

from hardware_probe.tier import decide_tier


class TestDecideTier(unittest.TestCase):
    def test_high_tier(self):
        gpus = [{"dedicated": True, "vram_gb": 16.0}]
        result = decide_tier(32.0, gpus)
        self.assertEqual(result["tier"], "high")

    def test_mid_tier(self):
        gpus = [{"dedicated": True, "vram_gb": 8.0}]
        result = decide_tier(16.0, gpus)
        self.assertEqual(result["tier"], "mid")

    def test_low_tier_no_gpu(self):
        result = decide_tier(8.0, [])
        self.assertEqual(result["tier"], "low")

    def test_minimal_tier(self):
        result = decide_tier(4.0, [])
        self.assertEqual(result["tier"], "minimal")

    def test_integrated_gpu_does_not_count_as_vram_source(self):
        # dedicated=False (Intel iGPU) olduğu için vram_gb dolu olsa bile
        # tier hesaplamasına katılmamalı.
        gpus = [{"dedicated": False, "vram_gb": None}]
        result = decide_tier(16.0, gpus)
        self.assertEqual(result["tier"], "low")

    def test_high_ram_without_gpu_stays_low(self):
        result = decide_tier(64.0, [])
        self.assertEqual(result["tier"], "low")


if __name__ == "__main__":
    unittest.main()
