"""Navigator's filesystem tools — sandboxed.

Security: all paths are resolved relative to a root directory (default: the
user's home directory, overridable with the `NAVIGATOR_MCP_FS_ROOT`
environment variable — the tests use this), reduced to canonical form
(`os.path.realpath`) and verified not to escape the root — which blocks path
traversal (`..`, symlink) attacks. `write_file` additionally: can only write
over an existing file with `overwrite=true` (to prevent accidental
overwrites), and the parent directory must already exist (the tool does not
create directories on its own — to keep its scope limited to file content).
`delete_file` is irreversible and so does nothing without `confirm=true`.
`rename_file` applies the same sandbox check to both source and destination
and requires `overwrite=true` if the destination already exists (consistent
with `write_file`). All tools work on files only — deleting or renaming
directories is not supported (the scope is deliberately kept narrow).
"""
import json
import os

DEFAULT_ROOT = os.environ.get("NAVIGATOR_MCP_FS_ROOT", os.path.expanduser("~"))
MAX_READ_BYTES = 1_000_000  # ~1 MB — so large files don't drown the context
MAX_WRITE_BYTES = 1_000_000
MAX_LIST_ENTRIES = 500


class FilesystemError(Exception):
    """Raised when a filesystem tool hits an error (not found, outside the root, too large, ...)."""


def _resolve_within_root(path: str, root: str) -> str:
    """Resolve `path` against `root`; raise if it escapes the root."""
    root_real = os.path.realpath(root)
    candidate = path if os.path.isabs(path) else os.path.join(root_real, path)
    resolved = os.path.realpath(candidate)
    if resolved != root_real and not resolved.startswith(root_real + os.sep):
        raise FilesystemError(f"'{path}' escapes the permitted root directory ({root})")
    return resolved


def read_file(path: str, root: str = DEFAULT_ROOT) -> str:
    resolved = _resolve_within_root(path, root)
    if not os.path.isfile(resolved):
        raise FilesystemError(f"File not found: {path}")
    size = os.path.getsize(resolved)
    if size > MAX_READ_BYTES:
        raise FilesystemError(f"File too large ({size} bytes > {MAX_READ_BYTES} byte limit): {path}")
    try:
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as e:
        raise FilesystemError(f"Could not read file: {path} ({e})") from e


def write_file(path: str, content: str, overwrite: bool = False, root: str = DEFAULT_ROOT) -> str:
    resolved = _resolve_within_root(path, root)
    if os.path.isdir(resolved):
        raise FilesystemError(f"'{path}' is a directory, not a file")
    if os.path.exists(resolved) and not overwrite:
        raise FilesystemError(f"File already exists: {path} (overwrite=true is required to write over it)")
    parent = os.path.dirname(resolved)
    if not os.path.isdir(parent):
        raise FilesystemError(f"Parent directory does not exist: {path}")

    encoded = content.encode("utf-8")
    if len(encoded) > MAX_WRITE_BYTES:
        raise FilesystemError(f"Content too large ({len(encoded)} bytes > {MAX_WRITE_BYTES} byte limit): {path}")

    try:
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as e:
        raise FilesystemError(f"Could not write file: {path} ({e})") from e
    return f"{len(encoded)} bytes written: {path}"


def delete_file(path: str, confirm: bool = False, root: str = DEFAULT_ROOT) -> str:
    resolved = _resolve_within_root(path, root)
    if not os.path.exists(resolved):
        raise FilesystemError(f"File not found: {path}")
    if os.path.isdir(resolved):
        raise FilesystemError(f"'{path}' is a directory, not a file (deleting directories is not supported)")
    if not confirm:
        raise FilesystemError(f"Deletion is irreversible — confirm=true is required to confirm: {path}")

    try:
        os.remove(resolved)
    except OSError as e:
        raise FilesystemError(f"Could not delete file: {path} ({e})") from e
    return f"Deleted: {path}"


def rename_file(path: str, new_path: str, overwrite: bool = False, root: str = DEFAULT_ROOT) -> str:
    resolved = _resolve_within_root(path, root)
    resolved_new = _resolve_within_root(new_path, root)
    if not os.path.isfile(resolved):
        raise FilesystemError(f"File not found: {path}")
    if os.path.isdir(resolved_new):
        raise FilesystemError(f"'{new_path}' is a directory, it cannot be the destination file")
    if os.path.exists(resolved_new) and not overwrite:
        raise FilesystemError(
            f"Destination file already exists: {new_path} (overwrite=true is required to write over it)"
        )
    parent = os.path.dirname(resolved_new)
    if not os.path.isdir(parent):
        raise FilesystemError(f"Parent directory does not exist: {new_path}")

    try:
        os.replace(resolved, resolved_new)
    except OSError as e:
        raise FilesystemError(f"Could not rename file: {path} -> {new_path} ({e})") from e
    return f"Renamed: {path} -> {new_path}"


def list_directory(path: str = ".", root: str = DEFAULT_ROOT) -> list[dict]:
    resolved = _resolve_within_root(path, root)
    if not os.path.isdir(resolved):
        raise FilesystemError(f"Directory not found: {path}")
    try:
        names = sorted(os.listdir(resolved))
    except OSError as e:
        raise FilesystemError(f"Could not list directory: {path} ({e})") from e

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
            "Reads the contents of a file (read-only, sandboxed — only under "
            f"the '{root}' root directory, at most {MAX_READ_BYTES} bytes)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "A file path relative to the root, or absolute within the root",
                },
            },
            "required": ["path"],
        },
        handler=lambda path: read_file(path, root=root),
    )
    server.register_tool(
        name="list_directory",
        description=(
            "Lists the contents of a directory (read-only, sandboxed — only "
            f"under the '{root}' root directory)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "A directory path relative to the root, or absolute within the root (default: '.')",
                },
            },
            "required": [],
        },
        handler=lambda path=".": json.dumps(list_directory(path, root=root), ensure_ascii=False),
    )
    server.register_tool(
        name="write_file",
        description=(
            "Writes text content to a file (sandboxed — only under the "
            f"'{root}' root directory, at most {MAX_WRITE_BYTES} bytes). "
            "The parent directory must already exist; overwrite=true is "
            "required to write over an existing file."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "A file path relative to the root, or absolute within the root",
                },
                "content": {
                    "type": "string",
                    "description": "The text content to write to the file",
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Allow writing over an existing file (default: false)",
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
            "Deletes a file (sandboxed — only under the "
            f"'{root}' root directory). This operation is IRREVERSIBLE; it "
            "does nothing without confirm=true. Only files can be deleted, "
            "not directories."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "A file path relative to the root, or absolute within the root",
                },
                "confirm": {
                    "type": "boolean",
                    "description": "Confirm the deletion (default: false — nothing is deleted without confirmation)",
                },
            },
            "required": ["path"],
        },
        handler=lambda path, confirm=False: delete_file(path, confirm=confirm, root=root),
    )
    server.register_tool(
        name="rename_file",
        description=(
            "Renames/moves a file (sandboxed — both source and destination "
            f"must be under the '{root}' root directory). overwrite=true is "
            "required if the destination already exists. For files only, not "
            "directories."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The source file path",
                },
                "new_path": {
                    "type": "string",
                    "description": "The destination file path",
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Write over the destination file if it already exists (default: false)",
                },
            },
            "required": ["path", "new_path"],
        },
        handler=lambda path, new_path, overwrite=False: rename_file(
            path, new_path, overwrite=overwrite, root=root
        ),
    )
