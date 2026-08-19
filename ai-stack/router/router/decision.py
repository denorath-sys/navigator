"""Pure routing logic — no I/O, fully testable functions.

The thresholds and rules are a Phase 2 draft; they will be revised in
Phase 3+ as real usage data accumulates (which requests fail locally, user
feedback).
"""

PREFERENCES = ("balanced", "privacy", "cost", "speed")
LOW_CAPABILITY_TIERS = ("minimal", "low")

# A rough keyword set signalling that a request may need mcp-tools' tools
# (hardware / filesystem / Hyprland queries).
#
# Verified in real testing in ai-stack/assistant: on this machine
# (tier="low"), short requests that nonetheless need tools ("how many CPU
# cores are there?") used to fall through to local under the old heuristic
# that only looked at word count, and because the small local model has poor
# tool-use reliability (see assistant/README.md, "Local tool-use") it
# sometimes produced a wrong or irrelevant answer. Such requests are
# therefore counted as 'complex' too and routed to the cloud (on a low tier).
#
# Both English and Turkish keywords are listed on purpose: the documentation
# and code of this project are English, but the assistant answers the user in
# whatever language they write in, so a Turkish prompt must reach the same
# routing decision as its English equivalent. Adding a language here means
# adding its keywords, never replacing the existing ones.
TOOL_KEYWORDS = (
    # hardware
    "core",
    "cpu",
    "ram",
    "memory",
    "gpu",
    "graphics card",
    "hardware",
    "tier",
    "çekirdek",
    "bellek",
    "grafik kart",
    "donanım",
    # filesystem
    "file",
    "folder",
    "directory",
    "list",
    "dosya",
    "klasör",
    "dizin",
    "listele",
    # windows/desktop (Hyprland)
    "window",
    "workspace",
    "desktop",
    "pencere",
    "masaüstü",
    # generic tool hint
    "tool",
    "aracı",
    "aracını",
    "aracıyla",
)


def mentions_tool_keywords(prompt: str) -> bool:
    """Does the prompt mention a topic that may need mcp-tools' tools
    (hardware/files/windows) — a rough keyword scan. Not real intent
    classification (see the module docstring), but a more accurate first
    signal than word count."""
    lowered = prompt.lower()
    return any(keyword in lowered for keyword in TOOL_KEYWORDS)


def estimate_complexity(prompt: str) -> str:
    """A very rough draft heuristic: long/multi-line requests OR requests
    that may need tools count as 'complex'.

    Real classification (token count, history context length, real intent
    detection) will be tackled in Phase 3+.
    """
    if "\n" in prompt:
        return "complex"
    if len(prompt.split()) > 40:
        return "complex"
    if mentions_tool_keywords(prompt):
        return "complex"
    return "simple"


def local_unavailable_reason(ollama_available: bool | None) -> str:
    """Why the local model cannot be used, as precisely as the caller knows.

    This used to be one sentence for two different situations: "local model
    not ready (Ollama down or model not pulled)". Since Layer 6 of the image
    ships Ollama installed and enabled, that sentence led with the unlikely
    half — in practice the service is running and the model was simply never
    pulled. The two need different things from the user, `ollama pull` in one
    case and a service that is not running in the other, so they are no longer
    the same sentence.

    None means the caller did not say. The answer is then still vague, because
    the alternative is guessing at the user's machine, and this stack's habit
    is to say what is known and stop there.
    """
    if ollama_available is True:
        return (
            "local model not pulled: Ollama is running, but the model recommended "
            "for this machine is not installed (ollama pull)"
        )
    if ollama_available is False:
        return "local model unavailable: the Ollama service is not running"
    return "local model not ready (Ollama status not reported)"


def decide_route(
    hardware_tier: str,
    model_ready: bool,
    preference: str,
    complexity: str,
    ollama_available: bool | None = None,
) -> dict:
    if preference not in PREFERENCES:
        raise ValueError(f"Unknown preference: {preference!r} (valid: {PREFERENCES})")

    if not model_ready:
        return {
            "target": "cloud",
            "reasoning": local_unavailable_reason(ollama_available),
        }

    if preference == "privacy":
        return {
            "target": "local",
            "reasoning": "privacy preference: always local as long as the model is ready",
        }

    if preference == "cost":
        return {
            "target": "local",
            "reasoning": "cost preference: always local as long as the model is ready (free)",
        }

    if preference == "speed":
        if complexity == "complex" and hardware_tier in LOW_CAPABILITY_TIERS:
            return {
                "target": "cloud",
                "reasoning": (
                    "speed preference + complex/possibly tool-requiring request + low "
                    "hardware tier: the cloud can answer faster and more reliably"
                ),
            }
        return {
            "target": "local",
            "reasoning": "speed preference: the local model is enough, with no network latency",
        }

    # preference == "balanced" (the default)
    if complexity == "complex" and hardware_tier in LOW_CAPABILITY_TIERS:
        return {
            "target": "cloud",
            "reasoning": (
                "complex/possibly tool-requiring request + low hardware tier: the local "
                "model may be insufficient or its tool-use reliability may be poor"
            ),
        }
    return {
        "target": "local",
        "reasoning": "model is ready and the request is suitable for local",
    }
