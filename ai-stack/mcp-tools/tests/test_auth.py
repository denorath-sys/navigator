import unittest

from mcp_tools.auth import extract_bearer_token, generate_token, tokens_match


class TestGenerateToken(unittest.TestCase):
    def test_generates_nonempty_string(self):
        token = generate_token()
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 20)

    def test_generates_unique_tokens(self):
        self.assertNotEqual(generate_token(), generate_token())


class TestExtractBearerToken(unittest.TestCase):
    def test_extracts_valid_bearer_header(self):
        self.assertEqual(extract_bearer_token("Bearer abc123"), "abc123")

    def test_case_insensitive_scheme(self):
        self.assertEqual(extract_bearer_token("bearer abc123"), "abc123")
        self.assertEqual(extract_bearer_token("BEARER abc123"), "abc123")

    def test_none_header_returns_none(self):
        self.assertIsNone(extract_bearer_token(None))

    def test_empty_header_returns_none(self):
        self.assertIsNone(extract_bearer_token(""))

    def test_wrong_scheme_returns_none(self):
        self.assertIsNone(extract_bearer_token("Basic abc123"))

    def test_missing_token_returns_none(self):
        self.assertIsNone(extract_bearer_token("Bearer"))

    def test_malformed_header_returns_none(self):
        self.assertIsNone(extract_bearer_token("abc123"))


class TestTokensMatch(unittest.TestCase):
    def test_matching_tokens(self):
        self.assertTrue(tokens_match("secret", "secret"))

    def test_non_matching_tokens(self):
        self.assertFalse(tokens_match("wrong", "secret"))

    def test_none_provided_does_not_match(self):
        self.assertFalse(tokens_match(None, "secret"))

    def test_empty_provided_does_not_match(self):
        self.assertFalse(tokens_match("", "secret"))


if __name__ == "__main__":
    unittest.main()
