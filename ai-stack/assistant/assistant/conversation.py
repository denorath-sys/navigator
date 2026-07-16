"""assistant'ın konuşma orkestrasyonu.

`router --decide-only` ile route kararı alınır (local-runtime/cloud-bridge'i
BOŞ YERE çalıştırmadan — bkz. router/status.py "decide_only"), sonra hem
**cloud** hem **local** rotası GERÇEK bir tool-use döngüsü kurar:
mcp-tools'un `tools/list` çıktısı ilgili sağlayıcının tool formatına
çevrilir; model bir tool çağrısı döndürdükçe ilgili mcp-tools aracı
GERÇEKTEN çalıştırılır (bkz. mcp_client.py), sonuç geri beslenir — model
son bir metin yanıtı verene kadar tekrarlanır.

- **cloud**: Claude Messages API (`tool_use`/`tool_result` blokları). Tam
  araç setine erişir.
- **local**: Ollama `/api/chat` (OpenAI-benzeri `tool_calls` — gerçek
  makinede `llama3.2:3b` ile doğrulandı, bkz. local-runtime/README.md).
  Sadece SALT-OKUNUR araçlara erişir (`LOCAL_SAFE_TOOL_NAMES`) — gerçek
  testte 3B model, "sadece 'merhaba' de" gibi zararsız bir istekte bile
  kendiliğinden `write_file`'ı `overwrite=true` ile çağırmaya kalkıştı
  (sadece hedef bir dizin olduğu için mcp-tools katmanında hata verdi,
  başka bir yolda gerçekten dosya değiştirebilirdi). Bu, "sistemi
  değiştiren her eylem açık onay ister" ilkesinin gerçek bir ihlal riski
  olduğundan, yazma/silme/yeniden adlandırma araçları yerel modele HİÇ
  gösterilmiyor — cloud (Claude) çok daha güvenilir olduğundan tam erişimi
  koruyor.

**Konuşma geçmişi:** İkisi de aynı düz `history: [{"role", "content"}, ...]`
biçimini kullanır (sadece kullanıcı/asistan METİN turları — ne Claude'un
tool_use/tool_result blokları ne Ollama'nın tool_calls'ı geçmişe DAHİL
EDİLİR, sadece o turun içinde kalır). Bu, route bir konuşma içinde değişse
bile (örn. önce local, sonra cloud) geçmişin taşınabilir kalmasını sağlar.
"""
import json
import subprocess

from .mcp_client import MCPClient

ROUTER_CMD = ["python3", "-m", "router"]
LOCAL_RUNTIME_CMD = ["python3", "-m", "local_runtime"]
CLOUD_BRIDGE_CMD = ["python3", "-m", "cloud_bridge"]

SYSTEM_PROMPT = (
    "Sen Navigator OS'un işletim sistemine gömülü asistanısın. Kullanıcının "
    "SİSTEM/DONANIM hakkındaki sorularını sana verilen araçları kullanarak "
    "gerçek verilerle cevapla — asla tahmin etme veya uydurma. Ama kullanıcı "
    "önceki konuşmada söylediği bir şeyi (isim, tercih vb.) soruyorsa ARAÇ "
    "KULLANMA — doğrudan konuşma geçmişinden cevapla. Türkçe cevap ver, "
    "kısa ve net ol."
)
MAX_TOOL_ITERATIONS = 8
MAX_HISTORY_MESSAGES = 20  # ~10 kullanıcı/asistan turu — sınırsız büyümeyi engeller

# Yerel (güvenilirliği düşük, küçük) modele sadece salt-okunur araçlar
# gösterilir — bkz. run_local_turn() docstring'i, gerçek testte yakalanan
# halüsinasyon write_file çağrısı.
LOCAL_SAFE_TOOL_NAMES = frozenset(
    {
        "hardware_tier",
        "route_request",
        "read_file",
        "list_directory",
        "list_windows",
        "list_workspaces",
        "active_window",
    }
)


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


def _mcp_tools_to_ollama_tools(mcp_tools: list[dict]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["inputSchema"],
            },
        }
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


def _call_local_runtime_converse(payload: dict, cwd: str = "../local-runtime") -> dict:
    result = subprocess.run(
        LOCAL_RUNTIME_CMD + ["--converse"],
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
    history: list[dict] | None = None,
    cloud_bridge_cwd: str = "../cloud-bridge",
    max_tokens: int = 1024,
    max_iterations: int = MAX_TOOL_ITERATIONS,
) -> dict:
    """Claude ile gerçek bir tool-use döngüsü çalıştırır. Dönen sözlük:
    `{"content": str, "tool_calls": [...], "route": "cloud", "history": [...]}`.

    `history` (varsa) Claude'un mesaj listesinin başına eklenir — Claude
    önceki turları görür. Döndürülen `history`, bu turun düz metin
    özetini (tool_use/tool_result OLMADAN) önceki geçmişe ekler.
    """
    tools = _mcp_tools_to_claude_tools(mcp_client.list_tools())
    messages: list[dict] = list(history or []) + [{"role": "user", "content": prompt}]
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
            final_text = _extract_text(response["content"])
            return {
                "content": final_text,
                "tool_calls": tool_calls,
                "route": "cloud",
                "history": (history or [])
                + [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": final_text},
                ],
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


def run_local_turn(
    prompt: str,
    mcp_client: MCPClient,
    history: list[dict] | None = None,
    local_runtime_cwd: str = "../local-runtime",
    max_iterations: int = MAX_TOOL_ITERATIONS,
) -> dict:
    """Ollama (`/api/chat`) ile gerçek bir tool-use döngüsü çalıştırır —
    `run_cloud_turn()` ile aynı desen, sadece tool format farklı (Ollama
    OpenAI-benzeri `tool_calls` kullanır, Claude'un `tool_use` bloklarından
    farklı). Dönen sözlük: `{"content": str, "tool_calls": [...],
    "route": "local", "history": [...]}`.
    """
    safe_tools_list = [t for t in mcp_client.list_tools() if t["name"] in LOCAL_SAFE_TOOL_NAMES]
    tools = _mcp_tools_to_ollama_tools(safe_tools_list)
    schemas_by_name = {t["name"]: t["inputSchema"] for t in safe_tools_list}
    # Sistem promptu olmadan (gerçek testte gözlendi) 3B model basit
    # hafıza/sohbet sorularında bile gereksiz araç çağırmaya kalkışıyor —
    # cloud yoluyla tutarlılık için aynı SYSTEM_PROMPT burada da veriliyor.
    messages: list[dict] = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + list(history or [])
        + [{"role": "user", "content": prompt}]
    )
    tool_calls: list[dict] = []

    for _ in range(max_iterations):
        response = _call_local_runtime_converse(
            {"messages": messages, "tools": tools}, cwd=local_runtime_cwd
        )

        if response.get("status") == "unavailable":
            raise AssistantError(f"local-runtime kullanılamıyor: {response.get('reason')}")
        if response.get("status") == "error":
            raise AssistantError(f"Ollama hata döndü: {response.get('error')}")

        message = response["message"]
        messages.append(message)

        ollama_tool_calls = message.get("tool_calls") or []
        if not ollama_tool_calls:
            final_text = message.get("content", "")
            return {
                "content": final_text,
                "tool_calls": tool_calls,
                "route": "local",
                "history": (history or [])
                + [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": final_text},
                ],
            }

        for call in ollama_tool_calls:
            fn = call["function"]
            if fn["name"] not in schemas_by_name:
                # Model, kendisine gösterilmeyen bir aracı (örn.
                # write_file) halüsinasyonla çağırmaya kalkıştı — savunma
                # katmanı, mcp_client.call_tool()'a hiç ulaşmadan reddeder.
                tool_calls.append({"name": fn["name"], "input": fn.get("arguments") or {}})
                messages.append(
                    {
                        "role": "tool",
                        "content": f"Araç çağrısı reddedildi: '{fn['name']}' yerel modele açık değil.",
                    }
                )
                continue
            # llama3.2:3b gerçek testte sıfır-parametreli araçlara bile
            # halüsinasyon argümanlar uydurdu (örn. {"path": "..."},
            # {"": "null"}) — aracın inputSchema'sında olmayan anahtarları
            # eleyerek bu sınıf hatayı gerçekten önlüyoruz.
            schema = schemas_by_name[fn["name"]]
            allowed = set(schema.get("properties", {}).keys())
            args = {k: v for k, v in (fn.get("arguments") or {}).items() if k in allowed}
            tool_calls.append({"name": fn["name"], "input": args})
            try:
                result = mcp_client.call_tool(fn["name"], args)
                result_text = _extract_text(result["content"])
            except Exception as e:
                result_text = f"Araç çağrısı başarısız: {e}"
            # Ollama/llama3.2 tool_call_id eşleşmesi gerektirmiyor (gerçek
            # makinede doğrulandı) — sadece role:"tool" + content yeterli.
            messages.append({"role": "tool", "content": result_text})

    raise AssistantError(
        f"{max_iterations} tur sonunda model hâlâ araç çağırmaya devam ediyor "
        "(sonsuz döngü koruması)"
    )


def run_turn(
    prompt: str,
    mcp_client: MCPClient,
    history: list[dict] | None = None,
    preference: str = "balanced",
    router_cwd: str = "../router",
    local_runtime_cwd: str = "../local-runtime",
    cloud_bridge_cwd: str = "../cloud-bridge",
    max_tokens: int = 1024,
) -> dict:
    """Tek bir kullanıcı isteğini uçtan uca işler: router kararı ->
    (cloud veya local, ikisi de gerçek tool-use döngüsü). `history`
    verilirse (ve `MAX_HISTORY_MESSAGES`'a kırpılırsa) her iki yolda da
    bağlam olarak kullanılır; dönen sözlükteki `history` bir sonraki
    `run_turn()` çağrısına aynen geçirilebilir."""
    decision = decide_route(prompt, preference=preference, router_cwd=router_cwd)
    trimmed_history = (history or [])[-MAX_HISTORY_MESSAGES:]

    if decision["route"] == "cloud":
        result = run_cloud_turn(
            prompt,
            mcp_client,
            history=trimmed_history,
            cloud_bridge_cwd=cloud_bridge_cwd,
            max_tokens=max_tokens,
        )
    else:
        result = run_local_turn(
            prompt, mcp_client, history=trimmed_history, local_runtime_cwd=local_runtime_cwd
        )

    result["hardware_tier"] = decision["hardware_tier"]
    result["reasoning"] = decision["reasoning"]
    return result
