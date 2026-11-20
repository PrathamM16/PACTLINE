import base64
import json
import unittest

from app.security import AuthError, RateLimiter, hash_password, issue_token, verify_password, verify_token

SECRET = "unit-test-secret"
NOW = 1_800_000_000


def tamper(token, claims):
    header, _, signature = token.split(".")
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"{header}.{body}.{signature}"


class PasswordTest(unittest.TestCase):
    def test_correct_password_verifies(self):
        self.assertTrue(verify_password("correct-horse-1", hash_password("correct-horse-1")))

    def test_wrong_password_is_rejected(self):
        self.assertFalse(verify_password("wrong-password", hash_password("correct-horse-1")))

    def test_hashes_are_salted(self):
        self.assertNotEqual(hash_password("same-password-1"), hash_password("same-password-1"))

    def test_garbage_hash_is_rejected(self):
        self.assertFalse(verify_password("x", "not-a-hash"))

    def test_plaintext_is_not_stored(self):
        self.assertNotIn("correct-horse-1", hash_password("correct-horse-1"))


class TokenTest(unittest.TestCase):
    def test_valid_token_returns_claims(self):
        token = issue_token(SECRET, {"typ": "access", "sub": "u1"}, 60, NOW)
        self.assertEqual(verify_token(SECRET, token, "access", NOW + 1)["sub"], "u1")

    def test_expired_token_is_rejected(self):
        token = issue_token(SECRET, {"typ": "access"}, 60, NOW)
        with self.assertRaises(AuthError):
            verify_token(SECRET, token, "access", NOW + 61)

    def test_wrong_secret_is_rejected(self):
        token = issue_token(SECRET, {"typ": "access"}, 60, NOW)
        with self.assertRaises(AuthError):
            verify_token("other", token, "access", NOW + 1)

    def test_wrong_type_is_rejected(self):
        token = issue_token(SECRET, {"typ": "tool"}, 60, NOW)
        with self.assertRaises(AuthError):
            verify_token(SECRET, token, "access", NOW + 1)

    def test_tampered_claims_are_rejected(self):
        token = issue_token(SECRET, {"typ": "access", "sub": "u1"}, 60, NOW)
        forged = tamper(token, {"typ": "access", "sub": "admin", "exp": NOW + 999})
        with self.assertRaises(AuthError):
            verify_token(SECRET, forged, "access", NOW + 1)

    def test_none_algorithm_is_rejected(self):
        header = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode()
        body = base64.urlsafe_b64encode(json.dumps({"typ": "access", "exp": NOW + 99}).encode()).rstrip(b"=").decode()
        with self.assertRaises(AuthError):
            verify_token(SECRET, f"{header}.{body}.", "access", NOW)

    def test_malformed_token_is_rejected(self):
        with self.assertRaises(AuthError):
            verify_token(SECRET, "abc", "access", NOW)

    def test_empty_secret_refuses_to_issue(self):
        with self.assertRaises(AuthError):
            issue_token("", {"typ": "access"}, 60)

    def test_empty_secret_refuses_to_verify(self):
        with self.assertRaises(AuthError):
            verify_token("", "a.b.c", "access")


class RateLimiterTest(unittest.TestCase):
    def setUp(self):
        self.now = [0.0]
        self.limiter = RateLimiter(2, 10, lambda: self.now[0])

    def test_requests_within_limit_are_allowed(self):
        self.assertTrue(self.limiter.allow("ip") and self.limiter.allow("ip"))

    def test_request_over_limit_is_blocked(self):
        self.limiter.allow("ip")
        self.limiter.allow("ip")
        self.assertFalse(self.limiter.allow("ip"))

    def test_other_keys_are_independent(self):
        self.limiter.allow("a")
        self.limiter.allow("a")
        self.assertTrue(self.limiter.allow("b"))

    def test_window_expiry_allows_again(self):
        self.limiter.allow("ip")
        self.limiter.allow("ip")
        self.now[0] = 11.0
        self.assertTrue(self.limiter.allow("ip"))


if __name__ == "__main__":
    unittest.main()
