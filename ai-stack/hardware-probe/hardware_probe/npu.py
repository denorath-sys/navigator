"""NPU (Neural Processing Unit) tespiti — henüz uygulanmadı.

Intel VPU, AMD XDNA, Qualcomm Hexagon gibi NPU'lar için ortak bir Linux
sysfs/driver arayüzü yok; somut bir kernel API hedefi netleşince (Faz 3+)
gerçek tespit eklenecek.
"""


def probe_npu() -> dict:
    return {
        "present": False,
        "note": "NPU tespiti henüz uygulanmadı (Faz 3+)",
    }
