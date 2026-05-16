import re


def clean_discogs_artist_name(value: str | None) -> str | None:
    if not value:
        return None
    return ", ".join(re.sub(r"\s+\(\d+\)$", "", artist.strip()) for artist in value.split(","))


def clean_discogs_self_released_label(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"\(([^()]+?)\s+\(\d+\)\s+Self-Released\)", r"(\1 Self-Released)", value).strip()
