"""HMAC-SHA256 signature verification for LINE webhooks."""

import hmac
import hashlib
import base64


def verify_signature(raw_body: bytes, signature_header: str, channel_secret: str) -> bool:
    """
    Verify the X-Line-Signature header against the raw request body.

    LINE signs every webhook with HMAC-SHA256 using your channel secret.
    The signature in the header is base64-encoded.

    CRITICAL: Use the raw bytes of the body, not parsed JSON.
    Re-serializing changes whitespace and breaks the signature.

    Uses constant-time comparison to prevent timing attacks.
    """
    if not signature_header:
        return False

    expected_digest = hmac.new(
        channel_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).digest()
    expected_b64 = base64.b64encode(expected_digest).decode("utf-8")

    return hmac.compare_digest(expected_b64, signature_header)
