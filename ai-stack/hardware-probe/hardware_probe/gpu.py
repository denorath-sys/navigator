"""GPU detection via /sys/class/drm — vendor, driver and (where possible) VRAM.

Known limitations (Phase 2 draft):
  - NVIDIA VRAM size cannot be read reliably from sysfs (the proprietary
    driver requires nvidia-smi); nvidia cards therefore return vram_gb=None
    but are still counted as "dedicated".
  - AMD integrated GPUs (APUs) also use the amdgpu driver, so they can be
    marked "dedicated" the same way a discrete Radeon card is — this
    distinction will be clarified later with a PCI device-id list.
"""
import os
import re

VENDOR_MAP = {
    "0x10de": "nvidia",
    "0x1002": "amd",
    "0x8086": "intel",
}

_CARD_RE = re.compile(r"^card\d+$")


def classify_vendor(vendor_id: str) -> str:
    return VENDOR_MAP.get(vendor_id.strip().lower(), "unknown")


def read_vram_gb(device_path: str, vendor: str) -> float | None:
    if vendor == "amd":
        try:
            with open(os.path.join(device_path, "mem_info_vram_total")) as f:
                return round(int(f.read().strip()) / (1024**3), 1)
        except (FileNotFoundError, ValueError):
            return None
    # nvidia: no reliable VRAM information in sysfs (see the module docstring)
    # intel: integrated GPU, no dedicated VRAM (it shares system RAM)
    return None


def probe_gpu_devices(drm_path: str = "/sys/class/drm") -> list[dict]:
    """Scan the cardN entries under /sys/class/drm (excluding connectors)."""
    devices = []
    if not os.path.isdir(drm_path):
        return devices

    for entry in sorted(os.listdir(drm_path)):
        if not _CARD_RE.match(entry):
            continue

        device_path = os.path.join(drm_path, entry, "device")
        vendor_file = os.path.join(device_path, "vendor")
        if not os.path.isfile(vendor_file):
            continue

        with open(vendor_file) as f:
            vendor_id = f.read().strip()
        vendor = classify_vendor(vendor_id)

        driver = "unknown"
        try:
            driver = os.path.basename(os.readlink(os.path.join(device_path, "driver")))
        except OSError:
            pass

        vram_gb = read_vram_gb(device_path, vendor)

        devices.append(
            {
                "card": entry,
                "vendor": vendor,
                "vendor_id": vendor_id,
                "driver": driver,
                "vram_gb": vram_gb,
                "dedicated": vendor in ("amd", "nvidia"),
            }
        )

    return devices
