import re
from typing import Any

_DIGITAL_RELEASE_FORMAT_TOKENS = frozenset(
    {
        "aac",
        "aiff",
        "alac",
        "ape",
        "dsd",
        "file",
        "flac",
        "m4a",
        "mp3",
        "ogg",
        "wav",
        "wma",
    }
)
_PHYSICAL_RELEASE_FORMAT_TOKENS = frozenset(
    {
        "7",
        "10",
        "12",
        "acetate",
        "bluray",
        "blu",
        "cassette",
        "cd",
        "cdr",
        "dvd",
        "flexi",
        "lathe",
        "lp",
        "minidisc",
        "sacd",
        "shellac",
        "vinyl",
    }
)


def is_likely_digital_release_format(value: Any) -> bool:
    tokens = _release_format_tokens(value)
    if not tokens:
        return False

    has_digital_format = bool(tokens & _DIGITAL_RELEASE_FORMAT_TOKENS)
    has_physical_format = bool(tokens & _PHYSICAL_RELEASE_FORMAT_TOKENS)
    return has_digital_format and not has_physical_format


def _release_format_tokens(value: Any) -> set[str]:
    values = value if isinstance(value, list) else [value]
    tokens: set[str] = set()
    for item in values:
        if not isinstance(item, str):
            continue
        tokens.update(token for token in re.split(r"[^a-z0-9]+", item.lower()) if token)
    return tokens
