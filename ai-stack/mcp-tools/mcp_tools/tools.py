"""Navigator'ın ilk MCP araçları — hardware-probe ve router'ı sarmalar.

Her iki araç da subprocess üzerinden ilgili modülün CLI'ını çağırır (bkz.
ai-stack/router/router/status.py'daki aynı desen) — Python import yerine
CLI kullanmak, gerçek sistemde ayrı süreçler olarak çalışacakları şekle
daha yakın.
"""
import subprocess

HARDWARE_PROBE_CMD = ["python3", "-m", "hardware_probe"]
ROUTER_CMD = ["python3", "-m", "router"]


def hardware_tier_tool(hardware_probe_path: str = "../hardware-probe") -> str:
    result = subprocess.run(
        HARDWARE_PROBE_CMD, cwd=hardware_probe_path, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def route_request_tool(
    prompt: str, prefer: str = "balanced", router_path: str = "../router"
) -> str:
    result = subprocess.run(
        ROUTER_CMD + ["--prompt", prompt, "--prefer", prefer],
        cwd=router_path,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def register_default_tools(
    server, hardware_probe_path: str = "../hardware-probe", router_path: str = "../router"
) -> None:
    server.register_tool(
        name="hardware_tier",
        description=(
            "Navigator'ın çalıştığı donanımın AI model tier'ını "
            "(minimal/low/mid/high) ve CPU/RAM/GPU sinyallerini döner."
        ),
        input_schema={"type": "object", "properties": {}},
        handler=lambda: hardware_tier_tool(hardware_probe_path),
    )
    server.register_tool(
        name="route_request",
        description=(
            "Bir kullanıcı isteğinin yerel model mi yoksa bulut mu ile "
            "karşılanması gerektiğine karar verir."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Yönlendirilecek istek"},
                "prefer": {
                    "type": "string",
                    "enum": ["balanced", "privacy", "cost", "speed"],
                    "default": "balanced",
                },
            },
            "required": ["prompt"],
        },
        handler=lambda prompt, prefer="balanced": route_request_tool(prompt, prefer, router_path),
    )
