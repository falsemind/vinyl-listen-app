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
CATALOG_TOKEN_PATTERN = re.compile(
    r"(?<![A-Z0-9])"
    r"(?:[A-Z]{3,}[A-Z0-9]*#[A-Z0-9]*\d[A-Z0-9]*"
    r"|[A-Z]{2,}[A-Z0-9]*(?:[-/.]?[A-Z0-9]+)*\d[A-Z0-9]*(?:[-/.]?[A-Z0-9]+)*"
    r"|[A-Z0-9]*\d[A-Z0-9]*(?:[-/.#][A-Z0-9]+)+)"
    r"(?![A-Z0-9])",
    re.IGNORECASE,
)
SPACED_CATALOG_TOKEN_PATTERN = re.compile(r"(?<![A-Z0-9])([A-Z]{2,}\s+\d{3,5})(?![A-Z0-9])", re.IGNORECASE)
SIDE_PREFIX_PATTERN = re.compile(r"^\s*[A-H][.)]\s+")
SEPARATOR_PATTERNS = (" - ", " / ", " – ", " — ", ": ")
EDGE_JUNK_CHARACTERS = " \t\r\n'\"“”‘’`-:#*/.,;|\\"
MAX_TEXT_FRAGMENTS = 8
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
            raw_text=raw_text,
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
        catalog_tokens = _extract_catalog_number_tokens(line)
        for token in catalog_tokens:
            _append_catalog_number_candidates(token, detected_catalog_numbers, seen)

        if catalog_tokens and not _line_starts_with_catalog_token(line):
            continue

        if _looks_like_catalog_number(line):
            _append_catalog_number_candidates(line, detected_catalog_numbers, seen)

    return tuple(_sort_catalog_number_candidates(detected_catalog_numbers))


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

    candidate_lines = _candidate_metadata_lines(cleaned_lines, blocked_values=blocked_values)
    scored_pair = _select_artist_title_pair(candidate_lines)
    if scored_pair is not None:
        return scored_pair
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

    for line in _candidate_metadata_lines(cleaned_lines, blocked_values=blocked_lines):
        lowered_line = line.lower()
        if lowered_line in blocked_lines or _looks_like_year_line(line):
            continue
        fragments.append(line)
        if len(fragments) == MAX_TEXT_FRAGMENTS:
            break

    return tuple(fragments)


def _candidate_metadata_lines(cleaned_lines: list[str], *, blocked_values: set[str]) -> list[str]:
    candidate_lines: list[str] = []
    seen: set[str] = set()

    for line in cleaned_lines:
        lowered_line = line.lower()
        if lowered_line in blocked_values:
            continue

        candidate = _clean_candidate_line(line)
        if candidate is None or candidate.lower() in blocked_values:
            continue
        if candidate.lower() in seen or not _is_strict_metadata_line(candidate):
            continue

        seen.add(candidate.lower())
        candidate_lines.append(candidate)

    return candidate_lines


def _looks_like_catalog_number(value: str) -> bool:
    cleaned_value = _clean_catalog_candidate(value)
    if cleaned_value is None:
        return False
    if len(cleaned_value) < 4 or len(cleaned_value) > 24:
        return False
    if _looks_like_track_listing(cleaned_value):
        return False
    if cleaned_value.isdigit():
        return False
    if _is_short_yearish_line(cleaned_value):
        return False
    if not any(character.isalpha() for character in cleaned_value):
        return False
    if not any(character.isdigit() for character in cleaned_value):
        return False
    if any(not (character.isalnum() or character.isspace() or character in "-/.#") for character in cleaned_value):
        return False
    if _is_labeled_metadata_line(cleaned_value):
        return False
    return len(cleaned_value.split()) <= 4 and (
        _line_starts_with_catalog_token(cleaned_value) or bool(_extract_catalog_number_tokens(cleaned_value))
    )


def _is_candidate_metadata_line(value: str) -> bool:
    lowered_value = value.lower()
    if len(value) < 3 or len(value) > 80:
        return False
    if lowered_value in NOISE_TERMS:
        return False
    if _looks_like_track_listing(value):
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

    if any(character.isdigit() for character in value):
        return False

    stripped_value = value.strip()
    if stripped_value and not stripped_value[0].isalnum():
        return False

    tokens = TOKEN_PATTERN.findall(value)
    alpha_tokens = [token for token in tokens if any(character.isalpha() for character in token)]
    if not alpha_tokens:
        return False
    if len(alpha_tokens[0]) <= 2 and not alpha_tokens[0].isupper():
        return False
    if len(alpha_tokens) == 1 and len(alpha_tokens[0]) < 3:
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


def _select_artist_title_pair(candidate_lines: list[str]) -> tuple[str, str] | None:
    if len(candidate_lines) < 2:
        return None

    best_pair: tuple[str, str] | None = None
    best_score: float | None = None

    for index, (artist, title) in enumerate(zip(candidate_lines, candidate_lines[1:], strict=False)):
        score = _metadata_line_quality(artist) + _metadata_line_quality(title) - min(index, 10) * 0.25
        if best_score is None or score > best_score:
            best_score = score
            best_pair = (artist, title)

    return best_pair


def _metadata_line_quality(value: str) -> float:
    tokens = TOKEN_PATTERN.findall(value)
    alpha_tokens = [token for token in tokens if any(character.isalpha() for character in token)]
    if not alpha_tokens:
        return 0.0

    score = sum(len(token) for token in alpha_tokens) / 3
    score += min(len(alpha_tokens), 3)

    if value.upper() == value and len(alpha_tokens) > 1:
        score += 3
    if value.upper().startswith("DJ "):
        score += 4
    if any(token.upper() in {"EP", "LP", "ALBUM", "SINGLE"} for token in alpha_tokens):
        score += 6
    if "&" in value or "/" in value:
        score += 2
    if len(alpha_tokens) == 1:
        score -= 2

    return score


def _clean_candidate_line(value: str) -> str | None:
    cleaned_value = " ".join(value.strip(EDGE_JUNK_CHARACTERS).split())
    cleaned_value = SIDE_PREFIX_PATTERN.sub("", cleaned_value)
    cleaned_value = " ".join(cleaned_value.strip(EDGE_JUNK_CHARACTERS).split())
    tokens = cleaned_value.split()
    if len(tokens) >= 3 and tokens[-1].isdigit() and all(token.isalpha() for token in tokens[:-1]):
        cleaned_value = " ".join(tokens[:-1])
    return cleaned_value or None


def _normalize_catalog_number(value: str) -> str | None:
    cleaned_value = _clean_catalog_candidate(value)
    return cleaned_value or None


def _clean_catalog_candidate(value: str) -> str | None:
    cleaned_value = " ".join(value.strip(EDGE_JUNK_CHARACTERS).split())
    cleaned_value = _strip_leading_lowercase_ocr_prefix(cleaned_value)
    cleaned_value = SIDE_PREFIX_PATTERN.sub("", cleaned_value)
    cleaned_value = " ".join(cleaned_value.strip(EDGE_JUNK_CHARACTERS).split())
    if " " not in cleaned_value and CATALOG_TOKEN_PATTERN.fullmatch(cleaned_value):
        cleaned_value = cleaned_value.upper()
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


def _sort_catalog_number_candidates(candidates: list[str]) -> list[str]:
    normalized_candidates = [_normalize_catalog_sort_token(candidate) for candidate in candidates]

    def sort_key(indexed_candidate: tuple[int, str]) -> tuple[int, int]:
        index, candidate = indexed_candidate
        normalized_candidate = normalized_candidates[index]
        suffix_penalty = int(
            any(
                other and normalized_candidate.endswith(other) and len(normalized_candidate) > len(other)
                for other in normalized_candidates
            )
        )
        space_penalty = int(" " in candidate and SPACED_CATALOG_TOKEN_PATTERN.fullmatch(candidate) is None)
        return suffix_penalty, space_penalty

    return [candidate for _, candidate in sorted(enumerate(candidates), key=sort_key)]


def _normalize_catalog_sort_token(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _extract_catalog_number_tokens(value: str) -> tuple[str, ...]:
    tokens: list[str] = []
    seen: set[str] = set()

    for match in SPACED_CATALOG_TOKEN_PATTERN.finditer(value):
        token = _clean_catalog_candidate(match.group(1))
        if token is None or token.lower() in seen:
            continue
        if _extract_year_from_value(token) is not None:
            continue
        seen.add(token.lower())
        tokens.append(token)

    for match in CATALOG_TOKEN_PATTERN.finditer(value):
        token = _clean_catalog_candidate(_strip_leading_lowercase_ocr_prefix(match.group(0)))
        if token is None:
            continue
        token = token.upper()
        if len(token) < 4 or token.lower() in seen:
            continue
        seen.add(token.lower())
        tokens.append(token)

    return tuple(tokens)


def _line_starts_with_catalog_token(value: str) -> bool:
    cleaned_value = _clean_catalog_candidate(value)
    if cleaned_value is None:
        return False

    first_token = cleaned_value.split()[0]
    return bool(CATALOG_TOKEN_PATTERN.fullmatch(first_token.upper()))


def _strip_leading_lowercase_ocr_prefix(value: str) -> str:
    if len(value) >= 2 and value[0].islower() and value[1].isupper():
        return value[1:]
    return value


def _looks_like_track_listing(value: str) -> bool:
    if SIDE_PREFIX_PATTERN.match(value):
        return True

    tokens = TOKEN_PATTERN.findall(value)
    if len(tokens) >= 2 and tokens[0].isdigit() and all(token.isalpha() for token in tokens[1:]):
        return True

    return len(tokens) >= 3 and tokens[-1].isdigit() and all(token.isalpha() for token in tokens[:-1])


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
        if character.isspace():
            return False
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
