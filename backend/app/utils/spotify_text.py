import hashlib
import re
import unicodedata
from collections.abc import Sequence


def normalize_spotify_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[^\w\s]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def stable_spotify_key(parts: Sequence[str | None]) -> str:
    return hashlib.sha256("|".join(part or "" for part in parts).encode("utf-8")).hexdigest()
