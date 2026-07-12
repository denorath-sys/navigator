"""Hyprland compositor durumunu sorgulayan araçlar — salt-okunur.

`hyprctl`'in JSON çıktı modunu (`hyprctl -j <komut>`) sarmalar. Bilinçli
olarak sadece SORGU var — workspace değiştirme, pencere kapatma/taşıma
gibi dispatch komutları YOK (kapsam Faz 2'de bilinçli olarak dar
tutuldu, bkz. mcp-tools/README.md "Kapsam dışı").

**Bilinen sınırlama:** Geliştirme ortamı Debian/Pardus olduğundan
(Hyprland bu dağıtımda paketli değil) bu araçlar GERÇEK bir Hyprland
compositor'a karşı test edilemedi — sadece mock'lanmış subprocess
testleriyle doğrulandı (bkz. `hyprland/README.md`'deki aynı sınırlama,
`hyprland.conf`'un statik incelemesi için). Gerçek doğrulama Faz 3'te
Navigator imajı üzerinde yapılacak.
"""
import json
import os
import shutil
import subprocess

HYPRCTL_BIN = "hyprctl"
TIMEOUT = 5.0


class HyprlandError(Exception):
    """Hyprland'a ulaşılamadığında (kurulu değil, çalışmıyor, hyprctl hatası)."""


def _run_hyprctl(*args: str) -> object:
    if shutil.which(HYPRCTL_BIN) is None:
        raise HyprlandError("hyprctl bulunamadı — Hyprland kurulu değil")
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        raise HyprlandError("Hyprland çalışmıyor (HYPRLAND_INSTANCE_SIGNATURE ayarlı değil)")

    try:
        result = subprocess.run(
            [HYPRCTL_BIN, "-j", *args],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired as e:
        raise HyprlandError(f"hyprctl zaman aşımına uğradı: {e}") from e
    except OSError as e:
        raise HyprlandError(f"hyprctl çalıştırılamadı: {e}") from e

    if result.returncode != 0:
        raise HyprlandError(f"hyprctl hata döndü: {result.stderr.strip()}")

    try:
        return json.loads(result.stdout)
    except ValueError as e:
        raise HyprlandError(f"hyprctl çıktısı JSON değil: {e}") from e


def list_windows() -> list[dict]:
    return _run_hyprctl("clients")


def list_workspaces() -> list[dict]:
    return _run_hyprctl("workspaces")


def active_window() -> dict:
    return _run_hyprctl("activewindow")


def register_hyprland_tools(server) -> None:
    server.register_tool(
        name="list_windows",
        description="Açık Hyprland pencerelerini listeler (salt-okunur, hyprctl -j clients).",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=lambda: json.dumps(list_windows(), ensure_ascii=False),
    )
    server.register_tool(
        name="list_workspaces",
        description="Hyprland workspace'lerini listeler (salt-okunur, hyprctl -j workspaces).",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=lambda: json.dumps(list_workspaces(), ensure_ascii=False),
    )
    server.register_tool(
        name="active_window",
        description=(
            "Şu an odaklanmış Hyprland penceresinin bilgisini döner "
            "(salt-okunur, hyprctl -j activewindow)."
        ),
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=lambda: json.dumps(active_window(), ensure_ascii=False),
    )
