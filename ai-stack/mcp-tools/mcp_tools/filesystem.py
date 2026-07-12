"""Navigator'ın dosya sistemi araçları — sandbox'lanmış.

Güvenlik: Tüm yollar bir kök dizine (varsayılan: kullanıcının ev dizini,
`NAVIGATOR_MCP_FS_ROOT` ortam değişkeniyle geçersiz kılınabilir — testler
bunu kullanır) göre çözümlenir ve kanonik forma (`os.path.realpath`)
indirgenip kökün dışına çıkmadığı doğrulanır — path traversal (`..`,
symlink) saldırılarını engeller. `write_file` ek olarak: var olan bir
dosyanın üzerine ancak `overwrite=true` ile yazılabilir (yanlışlıkla
üzerine yazmayı engellemek için) ve üst dizin zaten var olmalı (araç
kendiliğinden dizin oluşturmaz — kapsamı dosya içeriğiyle sınırlı tutmak
için). `delete_file` geri alınamaz olduğundan `confirm=true` olmadan
çalışmaz. `rename_file` hem kaynak hem hedef için aynı sandbox
kontrolünü uygular ve hedef zaten varsa `overwrite=true` ister
(`write_file` ile tutarlı). Tüm araçlar sadece dosyalarla çalışır —
dizin silme/yeniden adlandırma desteklenmiyor (kapsam bilinçli olarak
dar tutuluyor).
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


def delete_file(path: str, confirm: bool = False, root: str = DEFAULT_ROOT) -> str:
    resolved = _resolve_within_root(path, root)
    if not os.path.exists(resolved):
        raise FilesystemError(f"Dosya bulunamadı: {path}")
    if os.path.isdir(resolved):
        raise FilesystemError(f"'{path}' bir dizin, dosya değil (dizin silme desteklenmiyor)")
    if not confirm:
        raise FilesystemError(f"Silme geri alınamaz — onaylamak için confirm=true gerekir: {path}")

    try:
        os.remove(resolved)
    except OSError as e:
        raise FilesystemError(f"Dosya silinemedi: {path} ({e})") from e
    return f"Silindi: {path}"


def rename_file(path: str, new_path: str, overwrite: bool = False, root: str = DEFAULT_ROOT) -> str:
    resolved = _resolve_within_root(path, root)
    resolved_new = _resolve_within_root(new_path, root)
    if not os.path.isfile(resolved):
        raise FilesystemError(f"Dosya bulunamadı: {path}")
    if os.path.isdir(resolved_new):
        raise FilesystemError(f"'{new_path}' bir dizin, hedef dosya olamaz")
    if os.path.exists(resolved_new) and not overwrite:
        raise FilesystemError(
            f"Hedef dosya zaten var: {new_path} (üzerine yazmak için overwrite=true gerekir)"
        )
    parent = os.path.dirname(resolved_new)
    if not os.path.isdir(parent):
        raise FilesystemError(f"Üst dizin yok: {new_path}")

    try:
        os.replace(resolved, resolved_new)
    except OSError as e:
        raise FilesystemError(f"Dosya yeniden adlandırılamadı: {path} -> {new_path} ({e})") from e
    return f"Yeniden adlandırıldı: {path} -> {new_path}"


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
    server.register_tool(
        name="delete_file",
        description=(
            "Bir dosyayı siler (sandbox'lı — sadece "
            f"'{root}' kök dizini altında). Bu işlem GERİ ALINAMAZ; "
            "confirm=true olmadan çalışmaz. Sadece dosyalar silinebilir, "
            "dizinler değil."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Kök dizine göre göreli veya kök içinde mutlak dosya yolu",
                },
                "confirm": {
                    "type": "boolean",
                    "description": "Silmeyi onayla (varsayılan: false — onaylanmadan hiçbir şey silinmez)",
                },
            },
            "required": ["path"],
        },
        handler=lambda path, confirm=False: delete_file(path, confirm=confirm, root=root),
    )
    server.register_tool(
        name="rename_file",
        description=(
            "Bir dosyayı yeniden adlandırır/taşır (sandbox'lı — hem kaynak "
            f"hem hedef '{root}' kök dizini altında olmalı). Hedef zaten "
            "varsa overwrite=true gerekir. Sadece dosyalar için, dizinler için değil."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Kaynak dosya yolu",
                },
                "new_path": {
                    "type": "string",
                    "description": "Hedef dosya yolu",
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Hedef dosya zaten varsa üzerine yaz (varsayılan: false)",
                },
            },
            "required": ["path", "new_path"],
        },
        handler=lambda path, new_path, overwrite=False: rename_file(
            path, new_path, overwrite=overwrite, root=root
        ),
    )
