import os
import tempfile
import unittest

from hardware_probe.gpu import classify_vendor, probe_gpu_devices


class TestClassifyVendor(unittest.TestCase):
    def test_known_vendors(self):
        self.assertEqual(classify_vendor("0x8086"), "intel")
        self.assertEqual(classify_vendor("0x1002"), "amd")
        self.assertEqual(classify_vendor("0x10de"), "nvidia")

    def test_unknown_vendor(self):
        self.assertEqual(classify_vendor("0xdead"), "unknown")


class TestProbeGpuDevices(unittest.TestCase):
    def _make_card(self, drm_root, name, vendor_id, driver_name, extra_files=None):
        device_dir = os.path.join(drm_root, name, "device")
        os.makedirs(device_dir)
        with open(os.path.join(device_dir, "vendor"), "w") as f:
            f.write(vendor_id + "\n")
        # Gerçek sysfs'te driver symlink'i /sys/bus/pci/drivers/<isim> gibi bir
        # yola işaret eder; son bileşen sürücü adının kendisidir.
        driver_target = os.path.join(drm_root, "_drivers_root", driver_name)
        os.makedirs(driver_target)
        os.symlink(driver_target, os.path.join(device_dir, "driver"))
        for fname, content in (extra_files or {}).items():
            with open(os.path.join(device_dir, fname), "w") as f:
                f.write(content)

    def test_intel_integrated_no_vram(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._make_card(tmp, "card0", "0x8086", "i915")
            devices = probe_gpu_devices(tmp)
            self.assertEqual(len(devices), 1)
            self.assertEqual(devices[0]["vendor"], "intel")
            self.assertEqual(devices[0]["driver"], "i915")
            self.assertIsNone(devices[0]["vram_gb"])
            self.assertFalse(devices[0]["dedicated"])

    def test_amd_dedicated_with_vram(self):
        with tempfile.TemporaryDirectory() as tmp:
            vram_bytes = 8 * 1024**3
            self._make_card(
                tmp,
                "card0",
                "0x1002",
                "amdgpu",
                extra_files={"mem_info_vram_total": str(vram_bytes)},
            )
            devices = probe_gpu_devices(tmp)
            self.assertEqual(devices[0]["vendor"], "amd")
            self.assertEqual(devices[0]["vram_gb"], 8.0)
            self.assertTrue(devices[0]["dedicated"])

    def test_nvidia_dedicated_without_vram_reading(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._make_card(tmp, "card0", "0x10de", "nvidia")
            devices = probe_gpu_devices(tmp)
            self.assertEqual(devices[0]["vendor"], "nvidia")
            self.assertIsNone(devices[0]["vram_gb"])
            self.assertTrue(devices[0]["dedicated"])

    def test_ignores_connector_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._make_card(tmp, "card0", "0x8086", "i915")
            os.makedirs(os.path.join(tmp, "card0-DP-1"))
            devices = probe_gpu_devices(tmp)
            self.assertEqual(len(devices), 1)

    def test_missing_drm_path_returns_empty(self):
        devices = probe_gpu_devices("/nonexistent/path/xyz")
        self.assertEqual(devices, [])


if __name__ == "__main__":
    unittest.main()
