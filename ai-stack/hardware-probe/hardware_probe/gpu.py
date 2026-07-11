"""GPU detection via /sys/class/drm — vendor, sürücü ve (mümkünse) VRAM.

Bilinen sınırlamalar (Faz 2 taslağı):
  - NVIDIA VRAM miktarı sysfs üzerinden güvenilir okunamıyor (proprietary
    sürücü nvidia-smi gerektirir); bu yüzden nvidia kartlarda vram_gb=None
    döner ama yine de "dedicated" (ayrık) kabul edilir.
  - AMD entegre GPU'lar (APU) da amdgpu sürücüsünü kullandığından, ayrık bir
    Radeon kart ile aynı şekilde "dedicated" işaretlenebilir — bu ayrım
    ileride PCI device-id listesiyle netleştirilecek.
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
    # nvidia: sysfs'te güvenilir VRAM bilgisi yok (bkz. modül docstring'i)
    # intel: entegre GPU, ayrık VRAM'ı yok (sistem RAM'ini paylaşır)
    return None


def probe_gpu_devices(drm_path: str = "/sys/class/drm") -> list[dict]:
    """/sys/class/drm altındaki cardN girişlerini tarar (connector'ları hariç tutar)."""
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
