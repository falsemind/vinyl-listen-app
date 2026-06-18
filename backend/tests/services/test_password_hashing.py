from app.services.password_hashing import (
    ARGON2ID_ALGORITHM,
    ARGON2ID_VERSION,
    Argon2idPasswordHasher,
    PasswordHashConfig,
)

FAST_CONFIG = PasswordHashConfig(
    time_cost=1,
    memory_cost=1024,
    parallelism=1,
    hash_len=16,
    salt_len=8,
)


def test_hash_password_returns_argon2id_metadata_and_verifies_password() -> None:
    hasher = Argon2idPasswordHasher(FAST_CONFIG)

    result = hasher.hash_password("correct horse battery staple")

    assert result.algorithm == ARGON2ID_ALGORITHM
    assert result.version == ARGON2ID_VERSION
    assert result.params == FAST_CONFIG.to_metadata()
    assert "correct horse" not in result.password_hash

    verification = hasher.verify_password(
        password="correct horse battery staple",
        password_hash=result.password_hash,
        algorithm=result.algorithm,
        version=result.version,
        params=result.params,
    )

    assert verification.is_valid is True
    assert verification.needs_rehash is False


def test_verify_password_rejects_wrong_password_and_unknown_algorithm() -> None:
    hasher = Argon2idPasswordHasher(FAST_CONFIG)
    result = hasher.hash_password("right-password")

    wrong_password = hasher.verify_password(
        password="wrong-password",
        password_hash=result.password_hash,
        algorithm=result.algorithm,
        version=result.version,
        params=result.params,
    )
    unknown_algorithm = hasher.verify_password(
        password="right-password",
        password_hash=result.password_hash,
        algorithm="bcrypt",
        version=result.version,
        params=result.params,
    )

    assert wrong_password.is_valid is False
    assert unknown_algorithm.is_valid is False


def test_verify_password_flags_hash_that_needs_rehash() -> None:
    old_config = FAST_CONFIG
    current_config = PasswordHashConfig(
        time_cost=2,
        memory_cost=2048,
        parallelism=1,
        hash_len=16,
        salt_len=8,
    )
    old_hasher = Argon2idPasswordHasher(old_config)
    current_hasher = Argon2idPasswordHasher(current_config)
    result = old_hasher.hash_password("right-password")

    verification = current_hasher.verify_password(
        password="right-password",
        password_hash=result.password_hash,
        algorithm=result.algorithm,
        version=result.version,
        params=result.params,
    )

    assert verification.is_valid is True
    assert verification.needs_rehash is True
