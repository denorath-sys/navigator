import unittest

from router.decision import decide_route, estimate_complexity


class TestEstimateComplexity(unittest.TestCase):
    def test_short_prompt_is_simple(self):
        self.assertEqual(estimate_complexity("merhaba nasılsın"), "simple")

    def test_long_prompt_is_complex(self):
        prompt = " ".join(["kelime"] * 50)
        self.assertEqual(estimate_complexity(prompt), "complex")

    def test_multiline_prompt_is_complex(self):
        self.assertEqual(estimate_complexity("satır1\nsatır2"), "complex")


class TestDecideRoute(unittest.TestCase):
    def test_model_not_ready_always_routes_cloud(self):
        for pref in ("balanced", "privacy", "cost", "speed"):
            decision = decide_route("high", model_ready=False, preference=pref, complexity="simple")
            self.assertEqual(decision["target"], "cloud")

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
