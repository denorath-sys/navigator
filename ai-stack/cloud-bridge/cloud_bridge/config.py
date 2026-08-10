"""User-level credential configuration — `~/.config/navigator/env`.

Why it exists: `/usr` is read-only in the Navigator image, so a file such as
`/usr/share/navigator/ai-stack/cloud-bridge/.env.local` cannot be created, and
the credential is not baked into the image either. That left "let the user put
the variable in their own session environment" as the only route, but the
chain that starts the assistant (Hyprland `exec-once` → Quickshell →
`Process` → `python3 -m router` → `python3 -m cloud_bridge`) inherits the
environment from the one the compositor was started in: when the graphical
session is opened from a greeter or a TTY login there is no portable way to
put a variable there.

The credential is therefore read from a file AT THE END OF THE CHAIN, by the
module that needs it. It requires no environment variable plumbing: because
the file is resolved relative to HOME, it works even when Quickshell's
environment is empty.

The file format was deliberately kept `source`-able by a shell (`KEY=VALUE`,
`#` comments, an optional `export ` prefix) — so the same file can both be
read here and be used in a terminal with
`set -a && source ~/.config/navigator/env && set +a`. But what reads it here
is NOT A SHELL: there is NO `$VAR` expansion, no command substitution and no
inline comment; the value is the whole of the text from `=` to the end of the
line (trimmed, with quotes stripped where present).
"""
import os
import re
from pathlib import Path
from typing import NamedTuple

# The file is named "env" — if Navigator settings beyond credentials are ever
# needed they should go in a separate file (e.g. config.toml); this one should
# keep the "environment variables source-able by a shell" contract.
CONFIG_RELATIVE_PATH = Path("navigator") / "env"

# Today ONLY these two keys are read. Other lines in the file are parsed but
# ignored — this file is not an imitation environment file, it is
# cloud-bridge's credential source.
CREDENTIAL_KEYS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")

# The file holds a secret: if any bit is set for group/other we REFUSE to read
# it (ssh's private-key behaviour). Reading it silently would mean the user
# never noticing that their API key is readable on a multi-user machine.
INSECURE_MODE_MASK = 0o077

_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

PROBLEM_INSECURE = "insecure_permissions"
PROBLEM_UNREADABLE = "unreadable"
PROBLEM_MALFORMED = "malformed_line"

# The reason returned by the CLI/status report when no credential is found.
# Because the panel shows this string to the user, "why there wasn't one" must
# be distinguishable: not being configured is not the same thing as having been
# REFUSED because of wrong permissions.
_PROBLEM_REASONS = {
    PROBLEM_INSECURE: "credentials_file_insecure",
    PROBLEM_UNREADABLE: "credentials_file_unreadable",
    PROBLEM_MALFORMED: "credentials_file_malformed",
}
REASON_NOT_CONFIGURED = "credentials_not_configured"

SOURCE_ENVIRONMENT = "environment"
SOURCE_FILE = "file"


class CredentialResolution(NamedTuple):
    """Where the credential came from (or why it did not).

    `values` contains only those CREDENTIAL_KEYS actually found; it is never
    logged or reported — callers report `source`, `path` and `problem`, not the
    values.
    """

    values: dict
    source: str | None
    path: Path
    problem: str | None

    @property
    def unavailable_reason(self) -> str:
        """The machine-readable reason reported when there is no credential."""
        if self.problem:
            base = self.problem.split(":", 1)[0]
            return _PROBLEM_REASONS.get(base, REASON_NOT_CONFIGURED)
        return REASON_NOT_CONFIGURED


def config_path(environ: dict | None = None) -> Path:
    """`$XDG_CONFIG_HOME/navigator/env`, yoksa `~/.config/navigator/env`.

    The XDG Base Directory spec: if XDG_CONFIG_HOME is undefined, empty OR not
    absolute, it is ignored and the default is used.
    """
    environ = os.environ if environ is None else environ
    xdg = environ.get("XDG_CONFIG_HOME", "")
    base = Path(xdg) if xdg.startswith("/") else Path(environ.get("HOME", "~")).expanduser() / ".config"
    return base / CONFIG_RELATIVE_PATH


def parse_env_text(text: str) -> tuple[dict, str | None]:
    """Parse `KEY=VALUE` lines → (values, problem).

    A malformed line does NOT STOP parsing (the user may have written the rest
    correctly), but the number of the first malformed line is returned as the
    problem so that it appears in the status report.
    """
    values: dict = {}
    problem: str | None = None

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export ") or line.startswith("export\t"):
            line = line[len("export ") :].strip()

        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not _KEY_RE.match(key):
            if problem is None:
                problem = f"{PROBLEM_MALFORMED}:{lineno}"
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value

    return values, problem


def resolve_credentials(
    environ: dict | None = None, path: Path | None = None
) -> CredentialResolution:
    """Resolve the credential from the environment, failing that from the
    configuration file.

    The ENVIRONMENT takes precedence: if any of CREDENTIAL_KEYS is defined in
    the environment, the file is never opened. That keeps the development flow
    using `set -a && source .env.local`, CI, and one-off
    `ANTHROPIC_API_KEY=... command` usages independent of the file; and a user
    who deliberately set the environment does not meet the file's permission
    warning.
    """
    environ = os.environ if environ is None else environ
    path = config_path(environ) if path is None else path

    from_env = {k: environ[k] for k in CREDENTIAL_KEYS if environ.get(k)}
    if from_env:
        return CredentialResolution(from_env, SOURCE_ENVIRONMENT, path, None)

    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        return CredentialResolution({}, None, path, None)
    except OSError:
        return CredentialResolution({}, None, path, PROBLEM_UNREADABLE)

    if mode & INSECURE_MODE_MASK:
        return CredentialResolution({}, None, path, PROBLEM_INSECURE)

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return CredentialResolution({}, None, path, PROBLEM_UNREADABLE)

    parsed, problem = parse_env_text(text)
    values = {k: parsed[k] for k in CREDENTIAL_KEYS if parsed.get(k)}
    return CredentialResolution(values, SOURCE_FILE if values else None, path, problem)
