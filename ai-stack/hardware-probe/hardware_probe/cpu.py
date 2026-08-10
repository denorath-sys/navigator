"""CPU detection from /proc/cpuinfo: logical/physical core counts and model."""


def parse_cpuinfo(text: str) -> dict:
    """Parse the contents of /proc/cpuinfo into core counts and model name."""
    model_name = None
    logical_count = 0
    core_ids_per_physical: dict[str, set[str]] = {}

    for block in text.split("\n\n"):
        fields = {}
        for line in block.splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()

        if "processor" not in fields:
            continue

        logical_count += 1
        if model_name is None and "model name" in fields:
            model_name = fields["model name"]

        phys_id = fields.get("physical id")
        core_id = fields.get("core id")
        if phys_id is not None and core_id is not None:
            core_ids_per_physical.setdefault(phys_id, set()).add(core_id)

    if core_ids_per_physical:
        physical_count = sum(len(cores) for cores in core_ids_per_physical.values())
    else:
        # If the physical id/core id fields are absent (some ARM/virtual
        # environments), assuming one core each is the safest fallback.
        physical_count = logical_count

    return {
        "model": model_name or "unknown",
        "cores_logical": logical_count,
        "cores_physical": physical_count,
    }


def read_cpu_info(proc_path: str = "/proc") -> dict:
    with open(f"{proc_path}/cpuinfo") as f:
        return parse_cpuinfo(f.read())
