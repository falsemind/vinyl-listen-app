import base64
import hashlib
import hmac
import os

from app.core.config import settings


class TokenCipherConfigurationError(Exception):
    """Raised when token encryption is not configured."""


class TokenCipherError(Exception):
    """Raised when token encryption or decryption fails."""


class TokenCipher:
    """Encrypt and authenticate provider tokens with an app-managed secret."""

    _VERSION = "v1"
    _NONCE_BYTES = 16
    _TAG_BYTES = 32

    def __init__(self, secret: str) -> None:
        if not secret.strip():
            raise TokenCipherConfigurationError("Token encryption key is not configured.")

        secret_bytes = secret.encode("utf-8")
        self._encryption_key = hmac.new(secret_bytes, b"provider-token-encryption", hashlib.sha256).digest()
        self._mac_key = hmac.new(secret_bytes, b"provider-token-authentication", hashlib.sha256).digest()

    @classmethod
    def from_settings(cls) -> "TokenCipher":
        if not settings.discogs_token_encryption_key:
            raise TokenCipherConfigurationError("Discogs token encryption key is not configured.")
        return cls(settings.discogs_token_encryption_key)

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            raise TokenCipherError("Cannot encrypt an empty token.")

        nonce = os.urandom(self._NONCE_BYTES)
        plaintext_bytes = plaintext.encode("utf-8")
        ciphertext = self._xor_with_keystream(plaintext_bytes, nonce)
        tag = self._tag(nonce=nonce, ciphertext=ciphertext)
        return ".".join(
            [
                self._VERSION,
                _encode(nonce),
                _encode(ciphertext),
                _encode(tag),
            ]
        )

    def decrypt(self, token: str) -> str:
        try:
            version, encoded_nonce, encoded_ciphertext, encoded_tag = token.split(".")
        except ValueError as error:
            raise TokenCipherError("Encrypted token has an invalid format.") from error

        if version != self._VERSION:
            raise TokenCipherError("Encrypted token has an unsupported version.")

        nonce = _decode(encoded_nonce)
        ciphertext = _decode(encoded_ciphertext)
        expected_tag = self._tag(nonce=nonce, ciphertext=ciphertext)
        actual_tag = _decode(encoded_tag)
        if not hmac.compare_digest(expected_tag, actual_tag):
            raise TokenCipherError("Encrypted token authentication failed.")

        plaintext_bytes = self._xor_with_keystream(ciphertext, nonce)
        try:
            return plaintext_bytes.decode("utf-8")
        except UnicodeDecodeError as error:
            raise TokenCipherError("Encrypted token payload is invalid.") from error

    def _tag(self, *, nonce: bytes, ciphertext: bytes) -> bytes:
        return hmac.new(self._mac_key, self._VERSION.encode("utf-8") + nonce + ciphertext, hashlib.sha256).digest()[
            : self._TAG_BYTES
        ]

    def _xor_with_keystream(self, payload: bytes, nonce: bytes) -> bytes:
        output = bytearray()
        counter = 0

        while len(output) < len(payload):
            counter_bytes = counter.to_bytes(8, "big")
            output.extend(hmac.new(self._encryption_key, nonce + counter_bytes, hashlib.sha256).digest())
            counter += 1

        return bytes(value ^ stream for value, stream in zip(payload, output, strict=False))


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except (UnicodeEncodeError, ValueError) as error:
        raise TokenCipherError("Encrypted token contains invalid base64.") from error
