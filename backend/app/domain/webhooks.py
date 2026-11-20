import hashlib
import hmac

SIGNATURE_PREFIX = "sha256="


def sign(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return SIGNATURE_PREFIX + digest


def verify_signature(secret: str, body: bytes, header: str | None) -> bool:
    if not secret or not header or not header.startswith(SIGNATURE_PREFIX):
        return False
    return hmac.compare_digest(sign(secret, body), header)


class DeliveryLog:
    def __init__(self):
        self._seen: set[str] = set()

    def register(self, delivery_id: str) -> bool:
        if delivery_id in self._seen:
            return False
        self._seen.add(delivery_id)
        return True
