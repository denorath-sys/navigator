"""NPU (Neural Processing Unit) detection — not implemented yet.

There is no common Linux sysfs/driver interface for NPUs such as Intel VPU,
AMD XDNA or Qualcomm Hexagon; real detection will be added once a concrete
kernel API target becomes clear (Phase 3+).
"""


def probe_npu() -> dict:
    return {
        "present": False,
        "note": "NPU detection not implemented yet (Phase 3+)",
    }
