import re


def clean_discogs_artist_name(value: str | None) -> str | None:
    return clean_discogs_identifier_suffix(value)


def clean_discogs_label_name(value: str | None) -> str | None:
    return clean_discogs_identifier_suffix(clean_discogs_self_released_label(value))


def clean_discogs_identifier_suffix(value: str | None) -> str | None:
    if not value:
        return None

    parts = [re.sub(r"\s+\(\d+\)$", "", part.strip()) for part in value.split(",")]
    return ", ".join(part for part in parts if part) or None


def clean_discogs_self_released_label(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"\(([^()]+?)\s+\(\d+\)\s+Self-Released\)", r"(\1 Self-Released)", value).strip()
