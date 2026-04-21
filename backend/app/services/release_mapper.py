from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InternalReleaseData:
    discogs_release_id: int
    artist: str
    title: str
    year: int | None
    label: str | None
    catalog_number: str | None
    barcode: str | None
    genres: list[str] | None
    styles: list[str] | None
    cover_image_url: str | None


def map_discogs_to_internal(raw_json: dict[str, Any]) -> InternalReleaseData:
    discogs_release_id = raw_json.get("id")
    title = _clean_string(raw_json.get("title"))

    if not isinstance(discogs_release_id, int):
        raise ValueError("Discogs payload is missing a valid integer 'id'.")
    if not title:
        raise ValueError("Discogs payload is missing a release title.")

    artist = _extract_artist(raw_json)
    if not artist:
        raise ValueError("Discogs payload is missing artist metadata.")

    labels = raw_json.get("labels")
    identifiers = raw_json.get("identifiers")

    return InternalReleaseData(
        discogs_release_id=discogs_release_id,
        artist=artist,
        title=title,
        year=_coerce_int(raw_json.get("year")),
        label=_extract_label_name(labels),
        catalog_number=_extract_catalog_number(labels),
        barcode=_extract_barcode(identifiers),
        genres=_normalize_string_list(raw_json.get("genres")),
        styles=_normalize_string_list(raw_json.get("styles")),
        cover_image_url=_extract_cover_image_url(raw_json),
    )


def _extract_artist(raw_json: dict[str, Any]) -> str | None:
    artists_sort = _clean_string(raw_json.get("artists_sort"))
    if artists_sort:
        return artists_sort

    artists = raw_json.get("artists")
    if not isinstance(artists, list):
        return None

    names = [_clean_string(artist.get("name")) for artist in artists if isinstance(artist, dict)]
    normalized_names = [name for name in names if name]
    return ", ".join(normalized_names) if normalized_names else None


def _extract_label_name(labels: Any) -> str | None:
    if not isinstance(labels, list):
        return None

    for label in labels:
        if not isinstance(label, dict):
            continue
        name = _clean_string(label.get("name"))
        if name:
            return name

    return None


def _extract_catalog_number(labels: Any) -> str | None:
    if not isinstance(labels, list):
        return None

    for label in labels:
        if not isinstance(label, dict):
            continue
        catalog_number = _clean_string(label.get("catno"))
        if catalog_number:
            return catalog_number

    return None


def _extract_barcode(identifiers: Any) -> str | None:
    if not isinstance(identifiers, list):
        return None

    for identifier in identifiers:
        if not isinstance(identifier, dict):
            continue
        identifier_type = _clean_string(identifier.get("type"))
        value = _clean_string(identifier.get("value"))
        if identifier_type and identifier_type.lower() == "barcode" and value:
            return value

    return None


def _extract_cover_image_url(raw_json: dict[str, Any]) -> str | None:
    direct_image = _clean_string(raw_json.get("cover_image")) or _clean_string(raw_json.get("thumb"))
    if direct_image:
        return direct_image

    images = raw_json.get("images")
    if not isinstance(images, list):
        return None

    for image in images:
        if not isinstance(image, dict):
            continue
        uri = _clean_string(image.get("uri")) or _clean_string(image.get("resource_url"))
        if uri:
            return uri

    return None


def _normalize_string_list(values: Any) -> list[str] | None:
    if not isinstance(values, list):
        return None

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean_string(value)
        if not cleaned or cleaned in seen:
            continue
        normalized.append(cleaned)
        seen.add(cleaned)

    return normalized or None


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)

    return None


def _clean_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    cleaned = value.strip()
    return cleaned or None
