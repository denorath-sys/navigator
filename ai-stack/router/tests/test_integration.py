import json
import os
import subprocess
import tempfile
import unittest


def _cloud_credentials_available() -> bool:
    """Are there credentials — by asking cloud-bridge's OWN resolution.

    Looking at environment variables is not enough here: the source may also be
    `~/.config/navigator/env`. Rather than duplicating the rule, we ask the
    real implementation, so the two places cannot diverge.
    """
    cloud_bridge_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "cloud-bridge",
    )
    try:
        result = subprocess.run(
            ["python3", "-m", "cloud_bridge"],
            cwd=cloud_bridge_dir, capture_output=True, text=True, timeout=30,
        )
        return bool(json.loads(result.stdout).get("credentials_configured"))
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


class TestRouterIntegration(unittest.TestCase):
    """Verifies that the router -> local-runtime -> hardware-probe AND
    router -> cloud-bridge chains work end to end with REAL subprocesses.

    On this machine Ollama is installed and running and the recommended model
    (llama3.2:3b) has been pulled (model_ready: true) — simple requests are now
    genuinely generated locally. Complex requests still fall through to
    cloud-bridge (since tier="low" counts as low capacity); with no Claude API
    credential, that path reports "unavailable".
    """

    def _run_router(self, prompt: str, extra_args: list[str] | None = None) -> dict:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = {k: v for k, v in os.environ.items() if not k.startswith("ANTHROPIC_")}
        # Clearing ANTHROPIC_* is not enough: cloud-bridge also reads the
        # credential from ~/.config/navigator/env (see cloud_bridge/config.py),
        # so the "no credentials" claim only holds when HOME points at an empty
        # directory too. Nothing else at this end of the chain needs HOME.
        env["HOME"] = os.path.join(tempfile.gettempdir(), "navigator-test-empty-home")
        env.pop("XDG_CONFIG_HOME", None)
        result = subprocess.run(
            ["python3", "-m", "router", "--prompt", prompt, *(extra_args or [])],
            cwd=here,
            capture_output=True,
            text=True,
            env=env,
            timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_decide_only_returns_decision_without_generating(self):
        report = self._run_router("Sadece 'hello' kelimesiyle cevap ver.", ["--decide-only"])
        self.assertIn(report["hardware_tier"], ("minimal", "low", "mid", "high"))
        self.assertEqual(report["route"], "local")
        self.assertNotIn("local_runtime", report)
        self.assertNotIn("cloud_bridge", report)

    def test_short_tool_prompt_decide_only_routes_cloud_on_this_low_tier_machine(self):
        """On this machine tier="low" — a short but tool-requiring request
        (e.g. a hardware question) is now counted as 'complex' not only by word
        count but also by mentions_tool_keywords(), and is routed to the cloud
        (see 'Local tool-use' in ai-stack/assistant/README.md — the small local
        model's tool-use reliability problem)."""
        report = self._run_router(
            "How many CPU cores does this machine have?", ["--decide-only"]
        )
        self.assertEqual(report["hardware_tier"], "low")
        self.assertEqual(report["complexity"], "complex")
        self.assertEqual(report["route"], "cloud")

    def test_simple_prompt_routes_local_with_real_generation(self):
        report = self._run_router("Sadece 'hello' kelimesiyle cevap ver.")
        self.assertIn(report["hardware_tier"], ("minimal", "low", "mid", "high"))
        self.assertTrue(report["model_ready"])
        self.assertEqual(report["route"], "local")

        self.assertIn("local_runtime", report)
        self.assertNotIn("cloud_bridge", report)
        self.assertEqual(report["local_runtime"]["status"], "ok")
        self.assertEqual(report["local_runtime"]["model"], "llama3.2:3b")
        self.assertIsInstance(report["local_runtime"]["content"], str)
        self.assertGreater(len(report["local_runtime"]["content"]), 0)

    def test_complex_prompt_routes_cloud(self):
        # Because tier="low" counts as "low capacity" on this machine, complex
        # (long) requests fall through to cloud-bridge even when the model is
        # ready.
        long_prompt = " ".join(["kelime"] * 50)
        report = self._run_router(long_prompt)
        self.assertEqual(report["complexity"], "complex")
        self.assertEqual(report["route"], "cloud")

        self.assertIn("cloud_bridge", report)
        self.assertNotIn("local_runtime", report)
        self.assertEqual(report["cloud_bridge"]["status"], "unavailable")
        self.assertEqual(report["cloud_bridge"]["reason"], "credentials_not_configured")


HAS_CLOUD_CREDENTIALS = _cloud_credentials_available()


class TestRouterCloudCredentialedIntegration(unittest.TestCase):
    """If a Claude API credential is present (cloud-bridge/.env.local sourced,
    or ~/.config/navigator/env exists), verifies that the
    router -> cloud-bridge chain works end to end with a REAL Claude API call.
    Skipped when there are no credentials (including in CI, since none are
    committed) — see cloud-bridge/README.md."""

    @unittest.skipUnless(HAS_CLOUD_CREDENTIALS, "Claude kimlik bilgisi yok")
    def test_complex_prompt_routes_cloud_with_real_generation(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        long_prompt = "Answer in one word: what is the capital of Turkey? " + " ".join(
            ["please"] * 45
        )
        result = subprocess.run(
            ["python3", "-m", "router", "--prompt", long_prompt],
            cwd=here,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)

        self.assertEqual(report["complexity"], "complex")
        self.assertEqual(report["route"], "cloud")
        self.assertIn("cloud_bridge", report)
        self.assertNotIn("local_runtime", report)
        self.assertEqual(report["cloud_bridge"]["status"], "ok")
        self.assertIn("ankara", report["cloud_bridge"]["content"].lower())


if __name__ == "__main__":
    unittest.main()
