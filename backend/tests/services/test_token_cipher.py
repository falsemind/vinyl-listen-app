import base64

import pytest

from app.services.token_cipher import TokenCipher, TokenCipherError


def test_token_cipher_round_trips_token_without_plaintext_storage() -> None:
    cipher = TokenCipher("test-secret")

    encrypted = cipher.encrypt("discogs-secret-token")

    assert encrypted != "discogs-secret-token"
    assert "discogs-secret-token" not in encrypted
    assert cipher.decrypt(encrypted) == "discogs-secret-token"


def test_token_cipher_rejects_tampered_token() -> None:
    cipher = TokenCipher("test-secret")
    encrypted = cipher.encrypt("discogs-secret-token")
    version, nonce, ciphertext, tag = encrypted.split(".")
    ciphertext_bytes = bytearray(_decode_urlsafe(ciphertext))
    ciphertext_bytes[0] ^= 0x01
    tampered_ciphertext = _encode_urlsafe(bytes(ciphertext_bytes))
    tampered = ".".join([version, nonce, tampered_ciphertext, tag])

    with pytest.raises(TokenCipherError):
        cipher.decrypt(tampered)


def _decode_urlsafe(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _encode_urlsafe(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
