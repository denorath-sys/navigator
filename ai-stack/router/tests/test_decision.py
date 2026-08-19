import unittest

from router.decision import decide_route, estimate_complexity, mentions_tool_keywords


class TestEstimateComplexity(unittest.TestCase):
    def test_short_prompt_is_simple(self):
        self.assertEqual(estimate_complexity("hello how are you"), "simple")

    def test_long_prompt_is_complex(self):
        prompt = " ".join(["word"] * 50)
        self.assertEqual(estimate_complexity(prompt), "complex")

    def test_multiline_prompt_is_complex(self):
        self.assertEqual(estimate_complexity("line1\nline2"), "complex")

    def test_short_tool_prompt_is_complex(self):
        self.assertEqual(estimate_complexity("How many CPU cores does this machine have?"), "complex")


class TestMentionsToolKeywords(unittest.TestCase):
    def test_hardware_keyword_detected(self):
        self.assertTrue(mentions_tool_keywords("How many CPU cores does this machine have?"))

    def test_filesystem_keyword_detected(self):
        self.assertTrue(mentions_tool_keywords("could you read that file"))

    def test_window_keyword_detected(self):
        self.assertTrue(mentions_tool_keywords("which window is active"))

    def test_case_insensitive(self):
        self.assertTrue(mentions_tool_keywords("RAM how much"))

    def test_plain_conversation_not_detected(self):
        self.assertFalse(mentions_tool_keywords("hello how are you, nice weather today"))

    def test_turkish_prompt_reaches_the_same_decision(self):
        """TOOL_KEYWORDS deliberately carries both languages: the assistant
        answers in whatever language the user writes in, so a Turkish prompt
        must be routed exactly like its English equivalent. If someone
        replaces the Turkish keywords with English ones instead of adding
        to them, this test is what breaks."""
        self.assertTrue(mentions_tool_keywords("Bu makinede kaç CPU çekirdeği var?"))
        self.assertTrue(mentions_tool_keywords("şu dosyayı okur musun"))
        self.assertFalse(mentions_tool_keywords("merhaba nasılsın, bugün havalar güzel"))


class TestDecideRoute(unittest.TestCase):
    def test_model_not_ready_always_routes_cloud(self):
        for pref in ("balanced", "privacy", "cost", "speed"):
            decision = decide_route("high", model_ready=False, preference=pref, complexity="simple")
            self.assertEqual(decision["target"], "cloud")

    def test_not_ready_says_which_kind_of_not_ready(self):
        """The two situations need different things from the user — one is
        `ollama pull`, the other is a service that is not running — and they
        used to share one sentence that named the unlikely half first. The
        image ships Ollama enabled, so in practice it is running and the model
        was never pulled."""
        running = decide_route(
            "high", model_ready=False, preference="balanced",
            complexity="simple", ollama_available=True,
        )["reasoning"]
        self.assertIn("not pulled", running)
        self.assertIn("ollama pull", running)

        down = decide_route(
            "high", model_ready=False, preference="balanced",
            complexity="simple", ollama_available=False,
        )["reasoning"]
        self.assertIn("not running", down)
        self.assertNotIn("pull", down)

        self.assertNotEqual(running, down)

    def test_not_ready_stays_vague_when_nobody_said(self):
        """A caller with a partial status dict gets the vague sentence rather
        than a guess or a crash — router/status.py passes .get() for exactly
        this reason."""
        unknown = decide_route(
            "high", model_ready=False, preference="balanced", complexity="simple",
        )["reasoning"]
        self.assertIn("not reported", unknown)

    def test_privacy_preference_stays_local_when_ready(self):
        decision = decide_route("low", model_ready=True, preference="privacy", complexity="complex")
        self.assertEqual(decision["target"], "local")

    def test_cost_preference_stays_local_when_ready(self):
        decision = decide_route("minimal", model_ready=True, preference="cost", complexity="complex")
        self.assertEqual(decision["target"], "local")

    def test_speed_preference_goes_cloud_for_complex_low_tier(self):
        decision = decide_route("low", model_ready=True, preference="speed", complexity="complex")
        self.assertEqual(decision["target"], "cloud")

    def test_speed_preference_stays_local_for_simple_request(self):
        decision = decide_route("low", model_ready=True, preference="speed", complexity="simple")
        self.assertEqual(decision["target"], "local")

    def test_balanced_complex_low_tier_goes_cloud(self):
        decision = decide_route("low", model_ready=True, preference="balanced", complexity="complex")
        self.assertEqual(decision["target"], "cloud")

    def test_balanced_simple_stays_local(self):
        decision = decide_route("mid", model_ready=True, preference="balanced", complexity="simple")
        self.assertEqual(decision["target"], "local")

    def test_balanced_complex_high_tier_stays_local(self):
        decision = decide_route("high", model_ready=True, preference="balanced", complexity="complex")
        self.assertEqual(decision["target"], "local")

    def test_unknown_preference_raises(self):
        with self.assertRaises(ValueError):
            decide_route("mid", model_ready=True, preference="unknown", complexity="simple")


if __name__ == "__main__":
    unittest.main()
