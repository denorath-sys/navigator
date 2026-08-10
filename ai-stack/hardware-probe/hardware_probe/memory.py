"""RAM detection from /proc/meminfo."""


def parse_meminfo(text: str) -> dict:
    total_kb = None
    for line in text.splitlines():
        if line.startswith("MemTotal:"):
            total_kb = int(line.split()[1])
            break

    if total_kb is None:
        raise ValueError("MemTotal field not found in meminfo")

    return {
        "total_kb": total_kb,
        "total_gb": round(total_kb / (1024 * 1024), 1),
    }


def read_memory_info(proc_path: str = "/proc") -> dict:
    with open(f"{proc_path}/meminfo") as f:
        return parse_meminfo(f.read())
