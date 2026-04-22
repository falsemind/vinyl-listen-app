from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime

from app.pipelines.identification.models import ExtractedIdentifiers

BARCODE_PATTERN = re.compile(r"(?<!\d)(?:\d[\s-]?){8,14}(?!\d)")
LABELED_CATALOG_PATTERN = re.compile(
    r"(?:cat(?:alog)?(?:\s*(?:no|number|#))?[:#\s-]+)([A-Z0-9][A-Z0-9 ./-]{2,31})",
    re.IGNORECASE,
)
LABELED_LABEL_PATTERN = re.compile(
    r"(?:record\s+label|label)[:#\s-]+(.+)",
    re.IGNORECASE,
)
YEAR_PATTERN = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
SEPARATOR_PATTERNS = (" - ", " / ", " – ", " — ", ": ")
LABEL_SUFFIX_TERMS = frozenset(
    {
        "records",
        "recordings",
        "music",
        "media",
        "audio",
        "sounds",
        "sound",
        "productions",
    }
)
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
YEAR_CONTEXT_TERMS = ("year", "released", "release year", "©", "℗", "(c)", "(p)")
NOISE_PREFIXES = (
    "mastered by",
    "pressed by",
    "distributed by",
    "manufactured by",
    "mixed by",
    "engineered by",
    "produced by",
    "recorded by",
    "published by",
    "licensed from",
)
MAX_PLAUSIBLE_YEAR = datetime.now(UTC).year + 1
CATALOG_OCR_CORRECTIONS = {
    "o": "0",
    "q": "0",
    "d": "0",
    "i": "1",
    "l": "1",
}


class IdentifierParser:
    def parse(self, raw_text: str, *, barcodes: Iterable[str] = ()) -> ExtractedIdentifiers:
        cleaned_lines = _clean_lines(raw_text)
        parsed_barcodes = _dedupe_barcodes((*barcodes, *_extract_barcodes(raw_text)))
        catalog_numbers = _extract_catalog_numbers(raw_text, cleaned_lines)
        year, blocked_year_lines = _extract_year(cleaned_lines)
        label, blocked_label_lines = _extract_label(cleaned_lines)
        blocked_lines = blocked_year_lines | blocked_label_lines
        artist, title = _extract_artist_and_title(cleaned_lines, blocked_values=blocked_lines)
        text_fragments = _extract_text_fragments(
            cleaned_lines,
            artist=artist,
            title=title,
            catalog_numbers=catalog_numbers,
            label=label,
            blocked_values=blocked_lines,
        )

        return ExtractedIdentifiers(
            barcodes=parsed_barcodes,
            catalog_numbers=catalog_numbers,
            artist=artist,
            title=title,
            year=year,
            label=label,
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
        _append_catalog_number_candidates(match.group(1), detected_catalog_numbers, seen)

    for line in cleaned_lines:
        if not _looks_like_catalog_number(line):
            continue

        _append_catalog_number_candidates(line, detected_catalog_numbers, seen)

    return tuple(detected_catalog_numbers)


def _extract_year(cleaned_lines: list[str]) -> tuple[int | None, set[str]]:
    for line in cleaned_lines:
        if not _looks_like_year_line(line):
            continue
        year = _extract_year_from_value(line)
        if year is not None:
            return year, {line.lower()}

    return None, set()


def _extract_label(cleaned_lines: list[str]) -> tuple[str | None, set[str]]:
    for line in cleaned_lines:
        match = LABELED_LABEL_PATTERN.match(line)
        if match is None:
            continue

        candidate = _normalize_label(match.group(1))
        if candidate and _looks_like_label_value(candidate):
            return candidate, {line.lower(), candidate.lower()}

    for index, line in enumerate(cleaned_lines[:-1]):
        next_line = cleaned_lines[index + 1]
        if not _looks_like_label_prefix(line) or not _is_label_suffix_line(next_line):
            continue

        candidate = _normalize_label(f"{line} {next_line}")
        if candidate and _looks_like_label_value(candidate):
            return candidate, {line.lower(), next_line.lower(), candidate.lower()}

    for line in cleaned_lines:
        candidate = _normalize_label(line)
        if candidate and _looks_like_label_value(candidate):
            return candidate, {line.lower(), candidate.lower()}

    return None, set()


def _extract_artist_and_title(
    cleaned_lines: list[str],
    *,
    blocked_values: set[str],
) -> tuple[str | None, str | None]:
    labeled_artist: str | None = None
    labeled_title: str | None = None

    for line in cleaned_lines:
        if line.lower() in blocked_values:
            continue

        lowered_line = line.lower()
        if lowered_line.startswith("artist:"):
            labeled_artist = _clean_label_value(line.split(":", maxsplit=1)[1], strict=True)
        elif lowered_line.startswith("title:"):
            labeled_title = _clean_label_value(line.split(":", maxsplit=1)[1], strict=True)

    if labeled_artist or labeled_title:
        return labeled_artist, labeled_title

    for line in cleaned_lines:
        if line.lower() in blocked_values:
            continue

        for separator in SEPARATOR_PATTERNS:
            if separator not in line:
                continue
            left, right = line.split(separator, maxsplit=1)
            artist = _clean_candidate_line(left)
            title = _clean_candidate_line(right)
            if artist and title and _is_strict_metadata_line(artist) and _is_strict_metadata_line(title):
                return artist, title

    candidate_lines = [
        line for line in cleaned_lines if line.lower() not in blocked_values and _is_strict_metadata_line(line)
    ]
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
    label: str | None,
    blocked_values: set[str],
) -> tuple[str, ...]:
    fragments: list[str] = []
    blocked_lines = {value.lower() for value in catalog_numbers if value}
    blocked_lines.update(blocked_values)
    if artist:
        blocked_lines.add(artist.lower())
    if title:
        blocked_lines.add(title.lower())

    if label:
        fragments.append(label)
        blocked_lines.add(label.lower())

    for line in cleaned_lines:
        lowered_line = line.lower()
        if lowered_line in blocked_lines or _looks_like_year_line(line):
            continue
        if not _is_strict_metadata_line(line):
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
    if _is_short_yearish_line(value):
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
    if lowered_value.startswith(NOISE_PREFIXES):
        return False
    if _looks_like_year_line(value):
        return False
    if _is_labeled_metadata_line(value):
        return False
    if BARCODE_PATTERN.fullmatch(value.replace(" ", "")) is not None:
        return False
    if _looks_like_catalog_number(value):
        return False
    return any(character.isalpha() for character in value)


def _is_strict_metadata_line(value: str) -> bool:
    if not _is_candidate_metadata_line(value):
        return False

    stripped_value = value.strip()
    if stripped_value and not stripped_value[0].isalnum():
        return False

    tokens = TOKEN_PATTERN.findall(value)
    alpha_tokens = [token for token in tokens if any(character.isalpha() for character in token)]
    if not alpha_tokens:
        return False

    short_alpha_tokens = [token for token in alpha_tokens if len(token) <= 2]
    if max(len(token) for token in alpha_tokens) < 3 and len(alpha_tokens) > 1:
        return False

    if sum(len(token) == 1 for token in alpha_tokens) > 1:
        return False

    if len(alpha_tokens) >= 3 and len(short_alpha_tokens) * 2 >= len(alpha_tokens):
        return False

    punctuation_count = sum(not character.isalnum() and not character.isspace() for character in value)
    return punctuation_count <= 3


def _clean_label_value(value: str, *, strict: bool = False) -> str | None:
    cleaned_value = _clean_candidate_line(value)
    if cleaned_value and (
        _is_strict_metadata_line(cleaned_value) if strict else _is_candidate_metadata_line(cleaned_value)
    ):
        return cleaned_value
    return None


def _clean_candidate_line(value: str) -> str | None:
    cleaned_value = " ".join(value.strip().split())
    return cleaned_value or None


def _normalize_catalog_number(value: str) -> str | None:
    cleaned_value = " ".join(value.strip(" -:#").split())
    return cleaned_value or None


def _normalize_label(value: str) -> str | None:
    cleaned_value = " ".join(value.strip(" -:#*/").split())
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
            "label:",
            "record label:",
        )
    )


def _append_catalog_number_candidates(
    value: str,
    detected_catalog_numbers: list[str],
    seen: set[str],
) -> None:
    for candidate in _catalog_number_variants(value):
        lowered_candidate = candidate.lower()
        if lowered_candidate in seen:
            continue
        seen.add(lowered_candidate)
        detected_catalog_numbers.append(candidate)


def _catalog_number_variants(value: str) -> tuple[str, ...]:
    normalized_value = _normalize_catalog_number(value)
    if normalized_value is None:
        return ()

    variants: list[str] = []
    seen: set[str] = set()
    trimmed_value = _trim_catalog_trailing_token(normalized_value)

    for base_variant in (trimmed_value, normalized_value):
        if base_variant is None:
            continue

        for candidate in (base_variant, _correct_catalog_number_ocr(base_variant)):
            if candidate is None:
                continue

            lowered_candidate = candidate.lower()
            if lowered_candidate in seen:
                continue
            seen.add(lowered_candidate)
            variants.append(candidate)

    return tuple(variants)


def _correct_catalog_number_ocr(value: str) -> str | None:
    corrected_characters: list[str] = []
    changed = False

    for index, character in enumerate(value):
        replacement = CATALOG_OCR_CORRECTIONS.get(character.lower())
        if replacement is None or not _has_adjacent_digit(value, index):
            corrected_characters.append(character)
            continue

        corrected_characters.append(replacement)
        changed = True

    if not changed:
        return None
    return "".join(corrected_characters)


def _trim_catalog_trailing_token(value: str) -> str | None:
    parts = value.split()
    if len(parts) < 2:
        return None

    trailing_token = parts[-1]
    leading_value = " ".join(parts[:-1])
    if len(trailing_token) != 1 or not trailing_token.isalnum():
        return None
    if not _looks_like_catalog_number(leading_value):
        return None
    return leading_value


def _has_adjacent_digit(value: str, index: int) -> bool:
    return _neighboring_digit(value, index, step=-1) or _neighboring_digit(value, index, step=1)


def _neighboring_digit(value: str, index: int, *, step: int) -> bool:
    cursor = index + step
    while 0 <= cursor < len(value):
        character = value[cursor]
        if character.isdigit():
            return True
        if character not in {" ", "-", "/", "."}:
            return False
        cursor += step
    return False


def _extract_year_from_value(value: str) -> int | None:
    for matched_year in YEAR_PATTERN.findall(value):
        year = int(matched_year)
        if 1900 <= year <= MAX_PLAUSIBLE_YEAR:
            return year
    return None


def _looks_like_year_line(value: str) -> bool:
    year = _extract_year_from_value(value)
    if year is None:
        return False

    lowered_value = value.lower()
    if any(term in lowered_value for term in YEAR_CONTEXT_TERMS):
        return True

    return _is_short_yearish_line(value) and BARCODE_PATTERN.search(value) is None


def _looks_like_label_prefix(value: str) -> bool:
    cleaned_value = _clean_candidate_line(value)
    if cleaned_value is None:
        return False
    return not (
        _looks_like_catalog_number(cleaned_value)
        or _looks_like_year_line(cleaned_value)
        or _is_labeled_metadata_line(cleaned_value)
    )


def _is_label_suffix_line(value: str) -> bool:
    cleaned_value = _clean_candidate_line(value)
    if cleaned_value is None:
        return False
    return cleaned_value.lower() in LABEL_SUFFIX_TERMS


def _looks_like_label_value(value: str) -> bool:
    lowered_value = value.lower()
    if len(value) < 4 or len(value) > 60:
        return False
    if not any(character.isalpha() for character in value):
        return False
    if _looks_like_catalog_number(value) or _looks_like_year_line(value) or _is_labeled_metadata_line(value):
        return False
    return any(lowered_value == suffix or lowered_value.endswith(f" {suffix}") for suffix in LABEL_SUFFIX_TERMS)


def _is_short_yearish_line(value: str) -> bool:
    if _extract_year_from_value(value) is None:
        return False

    value_without_year = YEAR_PATTERN.sub("", value.lower())
    alpha_count = sum(character.isalpha() for character in value_without_year)
    return alpha_count <= 2
