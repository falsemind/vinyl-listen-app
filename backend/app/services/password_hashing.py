from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type

from app.core.config import settings

ARGON2ID_ALGORITHM = "argon2id"
ARGON2ID_VERSION = 1


@dataclass(frozen=True)
class PasswordHashConfig:
    """Argon2id cost parameters for password hashing."""

    time_cost: int = settings.auth_password_argon2_time_cost
    memory_cost: int = settings.auth_password_argon2_memory_cost
    parallelism: int = settings.auth_password_argon2_parallelism
    hash_len: int = settings.auth_password_argon2_hash_len
    salt_len: int = settings.auth_password_argon2_salt_len

    def to_metadata(self) -> dict[str, int]:
        return {
            "time_cost": self.time_cost,
            "memory_cost": self.memory_cost,
            "parallelism": self.parallelism,
            "hash_len": self.hash_len,
            "salt_len": self.salt_len,
        }


@dataclass(frozen=True)
class PasswordHashResult:
    """Stored password hash plus versioned metadata."""

    password_hash: str
    algorithm: str
    version: int
    params: dict[str, int]


@dataclass(frozen=True)
class PasswordVerificationResult:
    """Password verification result used by auth flows."""

    is_valid: bool
    needs_rehash: bool = False


class Argon2idPasswordHasher:
    """Argon2id password hasher with explicit upgrade metadata."""

    def __init__(self, config: PasswordHashConfig | None = None) -> None:
        self._config = config or PasswordHashConfig()
        self._hasher = PasswordHasher(
            time_cost=self._config.time_cost,
            memory_cost=self._config.memory_cost,
            parallelism=self._config.parallelism,
            hash_len=self._config.hash_len,
            salt_len=self._config.salt_len,
            type=Type.ID,
        )

    def hash_password(self, password: str) -> PasswordHashResult:
        return PasswordHashResult(
            password_hash=self._hasher.hash(password),
            algorithm=ARGON2ID_ALGORITHM,
            version=ARGON2ID_VERSION,
            params=self._config.to_metadata(),
        )

    def verify_password(
        self,
        *,
        password: str,
        password_hash: str,
        algorithm: str,
        version: int,
        params: dict | None,
    ) -> PasswordVerificationResult:
        if algorithm != ARGON2ID_ALGORITHM or version != ARGON2ID_VERSION:
            return PasswordVerificationResult(is_valid=False)

        try:
            is_valid = self._hasher.verify(password_hash, password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return PasswordVerificationResult(is_valid=False)

        if not is_valid:
            return PasswordVerificationResult(is_valid=False)

        return PasswordVerificationResult(
            is_valid=True,
            needs_rehash=self._hasher.check_needs_rehash(password_hash) or _params_need_rehash(params, self._config),
        )


def _params_need_rehash(params: dict | None, config: PasswordHashConfig) -> bool:
    if not isinstance(params, dict):
        return True

    expected = config.to_metadata()
    return any(params.get(key) != value for key, value in expected.items())
