"""Tüm alt-probe'ları tek bir tier raporunda birleştirir."""
from . import cpu, gpu, memory, npu, tier

SCHEMA_VERSION = "0.1"


def run_probe(proc_path: str = "/proc", drm_path: str = "/sys/class/drm") -> dict:
    cpu_info = cpu.read_cpu_info(proc_path)
    mem_info = memory.read_memory_info(proc_path)
    gpu_devices = gpu.probe_gpu_devices(drm_path)
    npu_info = npu.probe_npu()
    tier_info = tier.decide_tier(mem_info["total_gb"], gpu_devices)

    return {
        "schema_version": SCHEMA_VERSION,
        "cpu": cpu_info,
        "memory": mem_info,
        "gpu": {
            "devices": gpu_devices,
            "has_dedicated_gpu": tier_info["has_dedicated_gpu"],
            "best_vram_gb": tier_info["best_gpu_vram_gb"],
        },
        "npu": npu_info,
        "tier": tier_info["tier"],
        "tier_reasoning": tier_info["reasoning"],
    }
