"""Navigator'ın dosya sistemi araçları — sandbox'lanmış.

Güvenlik: Tüm yollar bir kök dizine (varsayılan: kullanıcının ev dizini,
`NAVIGATOR_MCP_FS_ROOT` ortam değişkeniyle geçersiz kılınabilir — testler
bunu kullanır) göre çözümlenir ve kanonik forma (`os.path.realpath`)
indirgenip kökün dışına çıkmadığı doğrulanır — path traversal (`..`,
symlink) saldırılarını engeller. `write_file` ek olarak: var olan bir
dosyanın üzerine ancak `overwrite=true` ile yazılabilir (yanlışlıkla
üzerine yazmayı engellemek için) ve üst dizin zaten var olmalı (araç
kendiliğinden dizin oluşturmaz — kapsamı dosya içeriğiyle sınırlı tutmak
için). Silme/yeniden adlandırma hâlâ YOK.
"""
import json
import os

DEFAULT_ROOT = os.environ.get("NAVIGATOR_MCP_FS_ROOT", os.path.expanduser("~"))
MAX_READ_BYTES = 1_000_000  # ~1 MB — büyük dosyaları context'e boğmamak için
MAX_WRITE_BYTES = 1_000_000
MAX_LIST_ENTRIES = 500


class FilesystemError(Exception):
    """Dosya sistemi aracı bir hata ile karşılaştığında (bulunamadı, kök dışı, çok büyük vb.)."""


def _resolve_within_root(path: str, root: str) -> str:
    """`path`'i `root`'a göre çözümler; kök dışına çıkarsa hata fırlatır."""
    root_real = os.path.realpath(root)
    candidate = path if os.path.isabs(path) else os.path.join(root_real, path)
    resolved = os.path.realpath(candidate)
    if resolved != root_real and not resolved.startswith(root_real + os.sep):
        raise FilesystemError(f"'{path}' izin verilen kök dizinin ({root}) dışına çıkıyor")
    return resolved


def read_file(path: str, root: str = DEFAULT_ROOT) -> str:
    resolved = _resolve_within_root(path, root)
    if not os.path.isfile(resolved):
        raise FilesystemError(f"Dosya bulunamadı: {path}")
    size = os.path.getsize(resolved)
    if size > MAX_READ_BYTES:
        raise FilesystemError(f"Dosya çok büyük ({size} bayt > {MAX_READ_BYTES} bayt sınırı): {path}")
    try:
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as e:
        raise FilesystemError(f"Dosya okunamadı: {path} ({e})") from e


def write_file(path: str, content: str, overwrite: bool = False, root: str = DEFAULT_ROOT) -> str:
    resolved = _resolve_within_root(path, root)
    if os.path.isdir(resolved):
        raise FilesystemError(f"'{path}' bir dizin, dosya değil")
    if os.path.exists(resolved) and not overwrite:
        raise FilesystemError(f"Dosya zaten var: {path} (üzerine yazmak için overwrite=true gerekir)")
    parent = os.path.dirname(resolved)
    if not os.path.isdir(parent):
        raise FilesystemError(f"Üst dizin yok: {path}")

    encoded = content.encode("utf-8")
    if len(encoded) > MAX_WRITE_BYTES:
        raise FilesystemError(f"İçerik çok büyük ({len(encoded)} bayt > {MAX_WRITE_BYTES} bayt sınırı): {path}")

    try:
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as e:
        raise FilesystemError(f"Dosya yazılamadı: {path} ({e})") from e
    return f"{len(encoded)} bayt yazıldı: {path}"


def list_directory(path: str = ".", root: str = DEFAULT_ROOT) -> list[dict]:
    resolved = _resolve_within_root(path, root)
    if not os.path.isdir(resolved):
        raise FilesystemError(f"Dizin bulunamadı: {path}")
    try:
        names = sorted(os.listdir(resolved))
    except OSError as e:
        raise FilesystemError(f"Dizin listelenemedi: {path} ({e})") from e

    entries = []
    for name in names[:MAX_LIST_ENTRIES]:
        full = os.path.join(resolved, name)
        try:
            is_dir = os.path.isdir(full)
            size = None if is_dir else os.path.getsize(full)
        except OSError:
            is_dir = False
            size = None
        entries.append({"name": name, "is_directory": is_dir, "size_bytes": size})
    return entries


def register_filesystem_tools(server, root: str = DEFAULT_ROOT) -> None:
    server.register_tool(
        name="read_file",
        description=(
            "Bir dosyanın içeriğini okur (salt-okunur, sandbox'lı — sadece "
            f"'{root}' kök dizini altında, en fazla {MAX_READ_BYTES} bayt)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Kök dizine göre göreli veya kök içinde mutlak dosya yolu",
                },
            },
            "required": ["path"],
        },
        handler=lambda path: read_file(path, root=root),
    )
    server.register_tool(
        name="list_directory",
        description=(
            "Bir dizinin içeriğini listeler (salt-okunur, sandbox'lı — sadece "
            f"'{root}' kök dizini altında)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Kök dizine göre göreli veya kök içinde mutlak dizin yolu (varsayılan: '.')",
                },
            },
            "required": [],
        },
        handler=lambda path=".": json.dumps(list_directory(path, root=root), ensure_ascii=False),
    )
    server.register_tool(
        name="write_file",
        description=(
            "Bir dosyaya metin içerik yazar (sandbox'lı — sadece "
            f"'{root}' kök dizini altında, en fazla {MAX_WRITE_BYTES} bayt). "
            "Üst dizin zaten var olmalı; var olan bir dosyanın üzerine yazmak "
            "için overwrite=true gerekir."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Kök dizine göre göreli veya kök içinde mutlak dosya yolu",
                },
                "content": {
                    "type": "string",
                    "description": "Dosyaya yazılacak metin içerik",
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Var olan bir dosyanın üzerine yazmaya izin ver (varsayılan: false)",
                },
            },
            "required": ["path", "content"],
        },
        handler=lambda path, content, overwrite=False: write_file(
            path, content, overwrite=overwrite, root=root
        ),
    )
