# ai-stack/hardware-probe/

## What it does

At system start-up (or on demand) it scans the hardware and decides which
"model tier" Navigator can run: it collects signals such as CPU core
count/model, total RAM, GPU presence/vendor/VRAM (where possible) and NPU
presence (not yet implemented), and combines them into a single JSON report.

This tier decision will determine which model size (e.g. the 3B / 8B / 14B
parameter class) `local-runtime/` runs locally, and when `router/` routes to
`cloud-bridge/` (Phase 3+).

## Usage

No external dependencies, only Python 3.11+ (stdlib).

```sh
cd ai-stack/hardware-probe
python3 -m hardware_probe --pretty
```

Tests:

```sh
cd ai-stack/hardware-probe
python3 -m unittest discover -v -s tests
```

## Output schema (v0.1)

```json
{
  "schema_version": "0.1",
  "cpu": {"model": "...", "cores_logical": 6, "cores_physical": 6},
  "memory": {"total_kb": 16195024, "total_gb": 15.4},
  "gpu": {
    "devices": [
      {"card": "card0", "vendor": "intel", "vendor_id": "0x8086",
       "driver": "i915", "vram_gb": null, "dedicated": false}
    ],
    "has_dedicated_gpu": false,
    "best_vram_gb": 0.0
  },
  "npu": {"present": false, "note": "NPU detection not implemented yet (Phase 3+)"},
  "tier": "low",
  "tier_reasoning": "RAM 15.4 GB >= 8 but the mid threshold (16 GB + 6 GB VRAM) was not met"
}
```

Tier thresholds (documented inside `hardware_probe/tier.py`):

| Tier | Condition |
|---|---|
| `minimal` | RAM < 8 GB, no discrete GPU |
| `low` | RAM >= 8 GB, mid threshold not met |
| `mid` | RAM >= 16 GB and discrete GPU VRAM >= 6 GB |
| `high` | RAM >= 32 GB and discrete GPU VRAM >= 12 GB |

These thresholds are a draft; they will be retuned in Phase 3+ as
`local-runtime` produces real benchmark data.

## Known limitations

- VRAM size cannot be read from sysfs on NVIDIA cards (the proprietary
  driver requires `nvidia-smi`) — it returns `vram_gb: null`, but the card
  is still counted as `dedicated: true`.
- AMD integrated GPUs (APUs) also use the `amdgpu` driver, so they may be
  marked `dedicated: true` the same way a discrete Radeon card is.
  A distinction based on PCI device-id will be added later.
- There is no NPU detection (there is not yet a common sysfs interface for
  Intel VPU / AMD XDNA / Qualcomm Hexagon).

## Status

Phase 2 — the first implementation is complete. `cpu.py`, `memory.py`,
`gpu.py`, `npu.py`, `tier.py`, `probe.py` and the `python3 -m hardware_probe`
CLI all exist; 20 unit/integration tests pass, verified on real hardware
(Intel i5-8500, 15.4 GB RAM, integrated Intel GPU).
