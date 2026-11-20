import unittest

from app.domain.webhooks import DeliveryLog, sign, verify_signature

SECRET = "test-secret"
BODY = b'{"action":"closed"}'


class WebhookSignatureTest(unittest.TestCase):
    def test_valid_signature_is_accepted(self):
        self.assertTrue(verify_signature(SECRET, BODY, sign(SECRET, BODY)))

    def test_tampered_body_is_rejected(self):
        self.assertFalse(verify_signature(SECRET, b"{}", sign(SECRET, BODY)))

    def test_wrong_secret_is_rejected(self):
        self.assertFalse(verify_signature("other", BODY, sign(SECRET, BODY)))

    def test_missing_header_is_rejected(self):
        self.assertFalse(verify_signature(SECRET, BODY, None))

    def test_header_without_prefix_is_rejected(self):
        self.assertFalse(verify_signature(SECRET, BODY, "abc"))

    def test_empty_secret_is_rejected(self):
        self.assertFalse(verify_signature("", BODY, sign("", BODY)))

    def test_known_digest_matches_reference(self):
        expected = "sha256=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17"
        self.assertEqual(sign("It's a Secret to Everybody", b"Hello, World!"), expected)


class DeliveryLogTest(unittest.TestCase):
    def test_first_delivery_is_registered(self):
        self.assertTrue(DeliveryLog().register("d1"))

    def test_duplicate_delivery_is_rejected(self):
        log = DeliveryLog()
        log.register("d1")
        self.assertFalse(log.register("d1"))


if __name__ == "__main__":
    unittest.main()
