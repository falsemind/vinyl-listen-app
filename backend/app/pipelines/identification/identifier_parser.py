from __future__ import annotations

import re
from collections.abc import Iterable

from app.pipelines.identification.models import ExtractedIdentifiers

BARCODE_PATTERN = re.compile(r"(?<!\d)(?:\d[\s-]?){8,14}(?!\d)")
LABELED_CATALOG_PATTERN = re.compile(
    r"(?:cat(?:alog)?(?:\s*(?:no|number|#))?[:#\s-]+)([A-Z0-9][A-Z0-9 ./-]{2,31})",
    re.IGNORECASE,
)
SEPARATOR_PATTERNS = (" - ", " / ", " – ", " — ", ": ")
NOISE_TERMS = {
    "stereo",
    "mono",
    "side a",
    "side b",
    "33 rpm",
    "45 rpm",
    "rpm",
    "lp",
    "vinyl",
    "records",
    "made in",
    "barcode",
    "catalog",
    "cat no",
}


class IdentifierParser:
    def parse(self, raw_text: str, *, barcodes: Iterable[str] = ()) -> ExtractedIdentifiers:
        cleaned_lines = _clean_lines(raw_text)
        parsed_barcodes = _dedupe_barcodes((*barcodes, *_extract_barcodes(raw_text)))
        catalog_numbers = _extract_catalog_numbers(raw_text, cleaned_lines)
        artist, title = _extract_artist_and_title(cleaned_lines)
        text_fragments = _extract_text_fragments(
            cleaned_lines,
            artist=artist,
            title=title,
            catalog_numbers=catalog_numbers,
        )

        return ExtractedIdentifiers(
            barcodes=parsed_barcodes,
            catalog_numbers=catalog_numbers,
            artist=artist,
            title=title,
            text_fragments=text_fragments,
        )


def _clean_lines(raw_text: str) -> list[str]:
    cleaned_lines: list[str] = []
    seen: set[str] = set()

    for raw_line in raw_text.splitlines():
        line = " ".join(raw_line.strip().split())
        if not line:
            continue

        if line.lower() in seen:
            continue

        seen.add(line.lower())
        cleaned_lines.append(line)

    return cleaned_lines


def _extract_barcodes(raw_text: str) -> tuple[str, ...]:
    detected_barcodes: list[str] = []
    seen: set[str] = set()

    for match in BARCODE_PATTERN.finditer(raw_text):
        barcode = "".join(character for character in match.group(0) if character.isdigit())
        if not (8 <= len(barcode) <= 14) or barcode in seen:
            continue
        seen.add(barcode)
        detected_barcodes.append(barcode)

    return tuple(detected_barcodes)


def _dedupe_barcodes(barcodes: Iterable[str]) -> tuple[str, ...]:
    deduped: list[str] = []
    seen: set[str] = set()

    for barcode in barcodes:
        normalized_barcode = "".join(character for character in barcode if character.isdigit())
        if not (8 <= len(normalized_barcode) <= 14) or normalized_barcode in seen:
            continue
        seen.add(normalized_barcode)
        deduped.append(normalized_barcode)

    return tuple(deduped)


def _extract_catalog_numbers(raw_text: str, cleaned_lines: list[str]) -> tuple[str, ...]:
    detected_catalog_numbers: list[str] = []
    seen: set[str] = set()

    for match in LABELED_CATALOG_PATTERN.finditer(raw_text):
        candidate = _normalize_catalog_number(match.group(1))
        if not candidate or candidate.lower() in seen:
            continue
        seen.add(candidate.lower())
        detected_catalog_numbers.append(candidate)

    for line in cleaned_lines:
        if not _looks_like_catalog_number(line):
            continue

        candidate = _normalize_catalog_number(line)
        if not candidate or candidate.lower() in seen:
            continue
        seen.add(candidate.lower())
        detected_catalog_numbers.append(candidate)

    return tuple(detected_catalog_numbers)


def _extract_artist_and_title(cleaned_lines: list[str]) -> tuple[str | None, str | None]:
    labeled_artist: str | None = None
    labeled_title: str | None = None

    for line in cleaned_lines:
        lowered_line = line.lower()
        if lowered_line.startswith("artist:"):
            labeled_artist = _clean_label_value(line.split(":", maxsplit=1)[1])
        elif lowered_line.startswith("title:"):
            labeled_title = _clean_label_value(line.split(":", maxsplit=1)[1])

    if labeled_artist or labeled_title:
        return labeled_artist, labeled_title

    for line in cleaned_lines:
        for separator in SEPARATOR_PATTERNS:
            if separator not in line:
                continue
            left, right = line.split(separator, maxsplit=1)
            artist = _clean_candidate_line(left)
            title = _clean_candidate_line(right)
            if artist and title and _is_candidate_metadata_line(artist) and _is_candidate_metadata_line(title):
                return artist, title

    candidate_lines = [line for line in cleaned_lines if _is_candidate_metadata_line(line)]
    if len(candidate_lines) >= 2:
        return candidate_lines[0], candidate_lines[1]
    if len(candidate_lines) == 1:
        return None, candidate_lines[0]

    return None, None


def _extract_text_fragments(
    cleaned_lines: list[str],
    *,
    artist: str | None,
    title: str | None,
    catalog_numbers: tuple[str, ...],
) -> tuple[str, ...]:
    fragments: list[str] = []
    blocked_values = {value.lower() for value in catalog_numbers if value}
    if artist:
        blocked_values.add(artist.lower())
    if title:
        blocked_values.add(title.lower())

    for line in cleaned_lines:
        lowered_line = line.lower()
        if lowered_line in blocked_values:
            continue
        if not _is_candidate_metadata_line(line):
            continue
        fragments.append(line)
        if len(fragments) == 4:
            break

    return tuple(fragments)


def _looks_like_catalog_number(value: str) -> bool:
    if len(value) < 4 or len(value) > 24:
        return False
    if value.isdigit():
        return False
    if not any(character.isalpha() for character in value):
        return False
    if not any(character.isdigit() for character in value):
        return False
    if _is_labeled_metadata_line(value):
        return False
    return len(value.split()) <= 4


def _is_candidate_metadata_line(value: str) -> bool:
    lowered_value = value.lower()
    if len(value) < 3 or len(value) > 80:
        return False
    if lowered_value in NOISE_TERMS:
        return False
    if lowered_value.startswith(("http://", "https://", "www.")):
        return False
    if _is_labeled_metadata_line(value):
        return False
    if BARCODE_PATTERN.fullmatch(value.replace(" ", "")) is not None:
        return False
    if _looks_like_catalog_number(value):
        return False
    return any(character.isalpha() for character in value)


def _clean_label_value(value: str) -> str | None:
    cleaned_value = _clean_candidate_line(value)
    if cleaned_value and _is_candidate_metadata_line(cleaned_value):
        return cleaned_value
    return None


def _clean_candidate_line(value: str) -> str | None:
    cleaned_value = " ".join(value.strip().split())
    return cleaned_value or None


def _normalize_catalog_number(value: str) -> str | None:
    cleaned_value = " ".join(value.strip(" -:#").split())
    return cleaned_value or None


def _is_labeled_metadata_line(value: str) -> bool:
    lowered_value = value.lower()
    return lowered_value.startswith(
        (
            "artist:",
            "title:",
            "barcode:",
            "barcode ",
            "cat no:",
            "cat no ",
            "catalog:",
            "catalog ",
        )
    )
