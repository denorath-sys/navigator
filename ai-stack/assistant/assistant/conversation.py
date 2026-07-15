"""assistant'ın konuşma orkestrasyonu.

`router --decide-only` ile route kararı alınır (local-runtime/cloud-bridge'i
BOŞ YERE çalıştırmadan — bkz. router/status.py "decide_only"), sonra:

- **cloud** rotası: Claude ile gerçek bir tool-use döngüsü kurulur.
  mcp-tools'un `tools/list` çıktısı Claude'un `tools` formatına çevrilir;
  Claude bir `tool_use` bloğu döndürdükçe ilgili mcp-tools aracı GERÇEKTEN
  çağrılır (bkz. mcp_client.py), sonuç `tool_result` olarak Claude'a geri
  beslenir — Claude son bir metin yanıtı verene kadar tekrarlanır.
- **local** rotası: düz üretim, ARAÇ KULLANIMI YOK. Ollama'nın
  function-calling desteği bu istemcide implemente edilmedi — bu bilinçli
  bir sınırlama (bkz. README "Kapsam dışı"), gerçekmiş gibi gösterilmiyor.
"""
import json
import subprocess

from .mcp_client import MCPClient

ROUTER_CMD = ["python3", "-m", "router"]
LOCAL_RUNTIME_CMD = ["python3", "-m", "local_runtime"]
CLOUD_BRIDGE_CMD = ["python3", "-m", "cloud_bridge"]

SYSTEM_PROMPT = (
    "Sen Navigator OS'un işletim sistemine gömülü asistanısın. Kullanıcının "
    "sistemi hakkındaki sorularını, sana verilen araçları kullanarak gerçek "
    "verilerle cevapla — asla tahmin etme veya uydurma. Türkçe cevap ver."
)
MAX_TOOL_ITERATIONS = 8


class AssistantError(Exception):
    """Konuşma döngüsü sırasında geri alınamaz bir hata oluştuğunda."""


def decide_route(
    prompt: str, preference: str = "balanced", router_cwd: str = "../router"
) -> dict:
    result = subprocess.run(
        ROUTER_CMD + ["--prompt", prompt, "--prefer", preference, "--decide-only"],
        cwd=router_cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _mcp_tools_to_claude_tools(mcp_tools: list[dict]) -> list[dict]:
    return [
        {"name": t["name"], "description": t["description"], "input_schema": t["inputSchema"]}
        for t in mcp_tools
    ]


def _extract_text(content_blocks: list[dict]) -> str:
    return "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")


def _call_cloud_bridge_converse(payload: dict, cwd: str = "../cloud-bridge") -> dict:
    result = subprocess.run(
        CLOUD_BRIDGE_CMD + ["--converse"],
        cwd=cwd,
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def run_cloud_turn(
    prompt: str,
    mcp_client: MCPClient,
    cloud_bridge_cwd: str = "../cloud-bridge",
    max_tokens: int = 1024,
    max_iterations: int = MAX_TOOL_ITERATIONS,
) -> dict:
    """Claude ile gerçek bir tool-use döngüsü çalıştırır. Dönen sözlük:
    `{"content": str, "tool_calls": [{"name", "input"}, ...], "route": "cloud"}`.
    """
    tools = _mcp_tools_to_claude_tools(mcp_client.list_tools())
    messages: list[dict] = [{"role": "user", "content": prompt}]
    tool_calls: list[dict] = []

    for _ in range(max_iterations):
        response = _call_cloud_bridge_converse(
            {
                "messages": messages,
                "system": SYSTEM_PROMPT,
                "tools": tools,
                "max_tokens": max_tokens,
            },
            cwd=cloud_bridge_cwd,
        )

        if response.get("status") == "unavailable":
            raise AssistantError(f"cloud-bridge kullanılamıyor: {response.get('reason')}")
        if response.get("status") == "error":
            raise AssistantError(f"Claude API hata döndü: {response.get('error')}")

        messages.append({"role": "assistant", "content": response["content"]})

        if response.get("stop_reason") != "tool_use":
            return {
                "content": _extract_text(response["content"]),
                "tool_calls": tool_calls,
                "route": "cloud",
            }

        tool_results = []
        for block in response["content"]:
            if block.get("type") != "tool_use":
                continue
            tool_calls.append({"name": block["name"], "input": block["input"]})
            try:
                result = mcp_client.call_tool(block["name"], block["input"])
                result_text = _extract_text(result["content"])
                is_error = bool(result.get("isError", False))
            except Exception as e:
                result_text = f"Araç çağrısı başarısız: {e}"
                is_error = True
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": result_text,
                    "is_error": is_error,
                }
            )
        messages.append({"role": "user", "content": tool_results})

    raise AssistantError(
        f"{max_iterations} tur sonunda Claude hâlâ araç çağırmaya devam ediyor "
        "(sonsuz döngü koruması)"
    )


def run_local_turn(prompt: str, local_runtime_cwd: str = "../local-runtime") -> dict:
    """Yerel model ile düz üretim. ARAÇ KULLANIMI YOK — bilinçli bir
    sınırlama, bkz. modül docstring'i."""
    result = subprocess.run(
        LOCAL_RUNTIME_CMD + ["--prompt", prompt],
        cwd=local_runtime_cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(result.stdout)
    if report.get("status") != "ok":
        raise AssistantError(f"local-runtime kullanılamıyor: {report}")
    return {"content": report["content"], "tool_calls": [], "route": "local"}


def run_turn(
    prompt: str,
    mcp_client: MCPClient,
    preference: str = "balanced",
    router_cwd: str = "../router",
    local_runtime_cwd: str = "../local-runtime",
    cloud_bridge_cwd: str = "../cloud-bridge",
    max_tokens: int = 1024,
) -> dict:
    """Tek bir kullanıcı isteğini uçtan uca işler: router kararı ->
    (cloud ise tool-use döngüsü, local ise düz üretim)."""
    decision = decide_route(prompt, preference=preference, router_cwd=router_cwd)

    if decision["route"] == "cloud":
        result = run_cloud_turn(
            prompt, mcp_client, cloud_bridge_cwd=cloud_bridge_cwd, max_tokens=max_tokens
        )
    else:
        result = run_local_turn(prompt, local_runtime_cwd=local_runtime_cwd)

    result["hardware_tier"] = decision["hardware_tier"]
    result["reasoning"] = decision["reasoning"]
    return result
