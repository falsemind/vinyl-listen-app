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
    tampered_ciphertext = f"{ciphertext[:-1]}A" if ciphertext[-1] != "A" else f"{ciphertext[:-1]}B"
    tampered = ".".join([version, nonce, tampered_ciphertext, tag])

    with pytest.raises(TokenCipherError):
        cipher.decrypt(tampered)
