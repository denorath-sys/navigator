import unittest

from local_runtime.models import TIER_MODEL_MAP, recommend_model


class TestRecommendModel(unittest.TestCase):
    def test_minimal_tier_has_no_recommendation(self):
        self.assertIsNone(recommend_model("minimal"))

    def test_known_tiers_have_model_and_size(self):
        for tier in ("low", "mid", "high"):
            rec = recommend_model(tier)
            self.assertIn("model", rec)
            self.assertIn("approx_size_gb", rec)
            self.assertGreater(rec["approx_size_gb"], 0)

    def test_unknown_tier_raises(self):
        with self.assertRaises(ValueError):
            recommend_model("ultra")

    def test_all_tiers_covered(self):
        self.assertEqual(set(TIER_MODEL_MAP.keys()), {"minimal", "low", "mid", "high"})


if __name__ == "__main__":
    unittest.main()
