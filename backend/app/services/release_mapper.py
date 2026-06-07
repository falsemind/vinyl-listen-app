from dataclasses import dataclass
from typing import Any

from app.utils.discogs_display import clean_discogs_artist_name, clean_discogs_self_released_label


@dataclass(frozen=True)
class InternalReleaseData:
    discogs_release_id: int
    artist: str
    title: str
    year: int | None
    format: str | None
    label: str | None
    catalog_number: str | None
    barcode: str | None
    genres: list[str] | None
    styles: list[str] | None
    thumbnail_url: str | None
    cover_image_url: str | None


@dataclass(frozen=True)
class ReleaseSideOptionData:
    value: str
    label: str
    side: str
    disc_number: int | None = None


@dataclass(frozen=True)
class ReleaseTrackData:
    position: str
    title: str
    duration: str | None = None


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
        format=_extract_format(raw_json.get("formats")),
        label=_extract_label_name(labels),
        catalog_number=_extract_catalog_number(labels),
        barcode=_extract_barcode(identifiers),
        genres=_normalize_string_list(raw_json.get("genres")),
        styles=_normalize_string_list(raw_json.get("styles")),
        thumbnail_url=_clean_string(raw_json.get("thumb")),
        cover_image_url=_extract_cover_image_url(raw_json),
    )


def extract_release_sides(raw_discogs_json: dict[str, Any] | None) -> list[str]:
    sides: list[str] = []
    seen: set[str] = set()
    for option in extract_release_side_options(raw_discogs_json):
        if option.side not in seen:
            sides.append(option.side)
            seen.add(option.side)

    return sides


def extract_release_side_options(raw_discogs_json: dict[str, Any] | None) -> list[ReleaseSideOptionData]:
    tracklist = raw_discogs_json.get("tracklist") if isinstance(raw_discogs_json, dict) else None
    if not isinstance(tracklist, list):
        return []

    side_sequence: list[str] = []
    previous_side: str | None = None
    for track in tracklist:
        if not isinstance(track, dict):
            continue

        position = track.get("position")
        if not isinstance(position, str):
            continue

        prefix = _extract_side_prefix(position)
        if prefix and prefix != previous_side:
            side_sequence.append(prefix)
            previous_side = prefix

    duplicate_sides = {side for side in side_sequence if side_sequence.count(side) > 1}
    include_disc = bool(duplicate_sides)
    disc_number = 1
    sides_in_current_disc: set[str] = set()
    options: list[ReleaseSideOptionData] = []

    for side in side_sequence:
        if side in sides_in_current_disc:
            disc_number += 1
            sides_in_current_disc = set()
        sides_in_current_disc.add(side)

        value = f"{disc_number}:{side}" if include_disc else side
        label = f"Disc {disc_number} - Side {side}" if include_disc else f"Side {side}"
        options.append(
            ReleaseSideOptionData(
                value=value,
                label=label,
                side=side,
                disc_number=disc_number if include_disc else None,
            )
        )

    return options


def extract_release_tracklist(raw_discogs_json: dict[str, Any] | None) -> list[ReleaseTrackData]:
    tracklist = raw_discogs_json.get("tracklist") if isinstance(raw_discogs_json, dict) else None
    if not isinstance(tracklist, list):
        return []

    tracks: list[ReleaseTrackData] = []
    for track in tracklist:
        if not isinstance(track, dict):
            continue
        if track.get("type_") not in (None, "track"):
            continue

        position = _clean_string(track.get("position"))
        title = _clean_string(track.get("title"))
        if not position or not title:
            continue

        tracks.append(
            ReleaseTrackData(
                position=position,
                title=title,
                duration=_clean_string(track.get("duration")),
            )
        )

    return tracks


def _extract_side_prefix(position: str) -> str | None:
    trimmed = position.strip().upper()
    letters = []
    for char in trimmed:
        if char.isalpha():
            letters.append(char)
            continue
        if letters:
            break

    return "".join(letters) or None


def _extract_artist(raw_json: dict[str, Any]) -> str | None:
    artists_sort = _clean_string(raw_json.get("artists_sort"))
    if artists_sort:
        return clean_discogs_artist_name(artists_sort)

    artists = raw_json.get("artists")
    if not isinstance(artists, list):
        return None

    names = [
        clean_discogs_artist_name(name)
        for name in (_clean_string(artist.get("name")) for artist in artists if isinstance(artist, dict))
    ]
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
            return clean_discogs_self_released_label(name)

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


def _extract_format(formats: Any) -> str | None:
    if not isinstance(formats, list):
        return None

    values: list[str] = []
    for item in formats:
        if not isinstance(item, dict):
            continue

        name = _clean_string(item.get("name"))
        descriptions = _normalize_string_list(item.get("descriptions")) or []
        if name:
            values.append(", ".join([name, *descriptions]))

    return "; ".join(values) or None


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
