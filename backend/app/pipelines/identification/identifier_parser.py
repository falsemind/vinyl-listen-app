import re
from collections.abc import Iterable
from datetime import UTC, datetime

from app.pipelines.identification.models import ExtractedIdentifiers, IdentifierEvidence
from app.pipelines.identification.normalization import (
    GTIN_CHECKSUM_LENGTHS,
    is_valid_gtin,
    normalize_or_repair_ocr_barcode,
)

BARCODE_PATTERN = re.compile(r"(?<![A-Z0-9])(?:[0-9OQDILSB][\s-]?){8,14}(?![A-Z0-9])", re.IGNORECASE)
BARCODE_CONTEXT_PATTERN = re.compile(r"\b(?:barcode|ean|upc)\b", re.IGNORECASE)
CONTACT_NUMBER_CONTEXT_PATTERN = re.compile(
    r"^\s*(?:tel(?:ephone)?|phone|fax|info|mobile|contact|booking)\b|"
    r"\b(?:tel(?:ephone)?|phone|fax|info|mobile|contact|booking)\s*[:+]",
    re.IGNORECASE,
)
EMAIL_ADDRESS_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
URL_TEXT_PATTERN = re.compile(
    r"\b(?:https?://|www\.|[A-Z0-9-]+\.(?:com|net|org|co|uk|info|biz|io)\b)",
    re.IGNORECASE,
)
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
    r"|\d[A-Z]{2,}[A-Z0-9]*\d[A-Z0-9]*"
    r"|[A-Z]{2,}[A-Z0-9]*(?:[-/.]?[A-Z0-9]+)*\d[A-Z0-9]*(?:[-/.]?[A-Z0-9]+)*"
    r"|[A-Z0-9]*\d[A-Z0-9]*(?:[-/.#][A-Z0-9]+)+)"
    r"(?![A-Z0-9])",
    re.IGNORECASE,
)
OCR_CONFUSED_CATALOG_TOKEN_PATTERN = re.compile(
    r"(?<![A-Z0-9])([A-Z]{2,}[A-Z0-9OQDIL?]{2,}\?)(?![A-Z0-9])",
    re.IGNORECASE,
)
EDGE_CONFUSED_CATALOG_TOKEN_PATTERN = re.compile(
    r"(?<![A-Z0-9])([T][A-Z0-9OQDIL]{3,14}[G])(?![A-Z0-9])",
    re.IGNORECASE,
)
SPACED_CATALOG_TOKEN_PATTERN = re.compile(
    r"(?<![A-Z0-9])([A-Z]{2,}\s+\d{2,5}(?:LP|EP)?)(?![A-Z0-9])",
    re.IGNORECASE,
)
LIMITED_EDITION_CATALOG_TOKEN_PATTERN = re.compile(
    r"(?<![A-Z0-9])([A-Z]{2,}\s+LIMITED\s+\d{2,5}(?:LP|EP)?)(?![A-Z0-9])",
    re.IGNORECASE,
)
SPACED_CONFUSED_CATALOG_TOKEN_PATTERN = re.compile(
    r"(?<![A-Z0-9])([A-Z]{2,})\s+([OQDI0-9]{2,6}(?:LP|EP)?)\b",
    re.IGNORECASE,
)
SIDE_MARKER_PATTERN = r"(?:[A-H]{1,2}|[A-H](?:\d{1,2}|[IL]{1,3}|IV|V))"
CATALOG_SIDE_SUFFIX_PATTERN = re.compile(
    rf"\s*/\s*{SIDE_MARKER_PATTERN}\s*[-.]?\s*side\s*$",
    re.IGNORECASE,
)
SIDE_PREFIX_PATTERN = re.compile(rf"^\s*{SIDE_MARKER_PATTERN}[.):]?\s+", re.IGNORECASE)
TRACK_LISTING_PREFIX_PATTERN = re.compile(
    rf"^\s*{SIDE_MARKER_PATTERN}\s*[.),:]\s*(?=[A-Z0-9\"'“”‘’(])",
    re.IGNORECASE,
)
TRACK_SIDE_QUALIFIER_PATTERN = re.compile(r"^\(?\s*(?:there|here|this side|other side)\s*\)?\s*", re.IGNORECASE)
TRACK_SIDE_WORD_PREFIX_PATTERN = re.compile(r"^side\b[.)]?\s*", re.IGNORECASE)
TRACK_DURATION_SUFFIX_PATTERN = re.compile(r"\s+\d{1,2}:\d{2}(?::\d{2})?\s*$")
TRACK_NUMBER_SUFFIX_PATTERN = re.compile(r"\s+(0?[1-9]|[12]\d|30)\s*$")
SEPARATOR_PATTERNS = (" - ", " / ", " + ", " – ", " — ", ": ")
EDGE_JUNK_CHARACTERS = " \t\r\n'\"“”‘’`_-:#*/.,;|\\"
MAX_TEXT_FRAGMENTS = 8
MIN_ARTIST_TITLE_PAIR_SCORE = 6.0
MIN_RAW_BARCODE_DIGITS_FOR_OCR_REPAIR = 6
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
LABEL_INFIX_TERMS = frozenset({"records", "recordings", "productions"})
NOISE_TERMS = {
    "stereo",
    "mono",
    "this side",
    "other side",
    "that side",
    "side",
    "side a",
    "side b",
    "33 rpm",
    "45 rpm",
    "rpm",
    "lp",
    "vinyl",
    "limited edition",
    "records",
    "made in",
    "barcode",
    "catalog",
    "cat no",
}
YEAR_CONTEXT_TERMS = ("year", "released", "release year", "©", "℗", "(c)", "(p)")
COPYRIGHT_YEAR_RANGE_PATTERN = re.compile(
    r"^\s*(?:[©℗]|\([cp]\))?\s*(?:19|20)\d{2}\s*/\s*(?:19|20)\d{2}\s*$",
    re.IGNORECASE,
)
LICENSED_TERMS = ("licenced", "licensed")
AUTHORIZED_TERMS = ("authorised", "authorized")
UNAUTHORIZED_TERMS = ("unauthorised", "unauthorized")
NOISE_PREFIXES = (
    "all rights",
    "all tracks",
    "additional production",
    "broadcasting",
    "production",
    "productions",
    "for ",
    "by ",
    "a r",
    "mastered by",
    "pressed by",
    "distributed by",
    "distributed",
    "manufactured by",
    "manufactured",
    "mixed by",
    "engineered by",
    "produced by",
    "recorded by",
    "published by",
    *LICENSED_TERMS,
    "licensed from",
    *UNAUTHORIZED_TERMS,
)
LEGAL_RIGHTS_TERMS = frozenset(
    {
        *AUTHORIZED_TERMS,
        "broadcasting",
        "copyright",
        "copying",
        "performance",
        "prohibited",
        "reserved",
        "rights",
        *UNAUTHORIZED_TERMS,
    }
)
CREDIT_LINE_TERMS = (
    " written ",
    " produced ",
    " producer ",
    " produc ",
    " production ",
    " productions ",
    " compose mix ",
    " remixed ",
    " mixed ",
    " mastered ",
    " engineered ",
)
MAX_PLAUSIBLE_YEAR = datetime.now(UTC).year + 1
CATALOG_OCR_CORRECTIONS = {
    "o": "0",
    "q": "0",
    "d": "0",
    "i": "1",
    "l": "1",
}
CATALOG_TERMINAL_OCR_CORRECTIONS = {
    "?": "7",
}
CATALOG_EDGE_OCR_CORRECTIONS = {
    "t": "7",
    "g": "6",
}
CATALOG_SUFFIX_OCR_CORRECTIONS = {
    **CATALOG_OCR_CORRECTIONS,
    **CATALOG_TERMINAL_OCR_CORRECTIONS,
}
KNOWN_CATALOG_PREFIX_OCR_CORRECTIONS = {
    "SYSTEM": "SYSTM",
}


class IdentifierParser:
    def parse(self, raw_text: str, *, barcodes: Iterable[str] = ()) -> ExtractedIdentifiers:
        cleaned_lines = _clean_lines(raw_text)
        parsed_barcodes = _dedupe_barcodes((*barcodes, *_extract_barcodes(raw_text)))
        catalog_numbers = _extract_catalog_numbers(raw_text, cleaned_lines)
        year, blocked_year_lines = _extract_year(cleaned_lines)
        label, blocked_label_lines = _extract_label(cleaned_lines)
        blocked_catalog_lines = _catalog_source_lines(cleaned_lines, catalog_numbers)
        blocked_lines = blocked_year_lines | blocked_label_lines | blocked_catalog_lines
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
            identifier_evidence=_build_parser_evidence(
                barcodes=parsed_barcodes,
                catalog_numbers=catalog_numbers,
                artist=artist,
                title=title,
                year=year,
                label=label,
                text_fragments=text_fragments,
            ),
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

    for line in raw_text.splitlines():
        if _looks_like_contact_number_line(line):
            continue

        for match in BARCODE_PATTERN.finditer(line):
            matched_value = match.group(0)
            raw_digit_count = sum(character.isdigit() for character in matched_value)
            repaired_barcode = normalize_or_repair_ocr_barcode(matched_value)
            if (
                repaired_barcode is not None
                and raw_digit_count < MIN_RAW_BARCODE_DIGITS_FOR_OCR_REPAIR
                and BARCODE_CONTEXT_PATTERN.search(line) is None
            ):
                continue
            barcode = repaired_barcode or "".join(character for character in matched_value if character.isdigit())
            if (
                not _is_valid_ocr_barcode_candidate(
                    barcode,
                    line=line,
                    checksum_valid=repaired_barcode is not None,
                )
                or barcode in seen
            ):
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


def _build_parser_evidence(
    *,
    barcodes: tuple[str, ...],
    catalog_numbers: tuple[str, ...],
    artist: str | None,
    title: str | None,
    year: int | None,
    label: str | None,
    text_fragments: tuple[str, ...],
) -> tuple[IdentifierEvidence, ...]:
    evidence: list[IdentifierEvidence] = []
    evidence.extend(IdentifierEvidence(kind="barcode", value=value, source="parser") for value in barcodes)
    evidence.extend(
        IdentifierEvidence(kind="catalog_number", value=value, source="parser") for value in catalog_numbers
    )
    if artist:
        evidence.append(IdentifierEvidence(kind="artist", value=artist, source="parser"))
    if title:
        evidence.append(IdentifierEvidence(kind="title", value=title, source="parser"))
    if year is not None:
        evidence.append(IdentifierEvidence(kind="year", value=str(year), source="parser"))
    if label:
        evidence.append(IdentifierEvidence(kind="label", value=label, source="parser"))
    evidence.extend(IdentifierEvidence(kind="text_fragment", value=value, source="parser") for value in text_fragments)
    return tuple(evidence)


def _extract_catalog_numbers(raw_text: str, cleaned_lines: list[str]) -> tuple[str, ...]:
    detected_catalog_numbers: list[str] = []
    seen: set[str] = set()
    scores: dict[str, int] = {}
    noisy_ocr_text = _looks_like_noisy_ocr_text(cleaned_lines)

    for match in LABELED_CATALOG_PATTERN.finditer(raw_text):
        _append_catalog_number_candidates(match.group(1), detected_catalog_numbers, seen, scores)

    if not noisy_ocr_text:
        for token in _extract_adjacent_catalog_number_tokens(cleaned_lines):
            _append_catalog_number_candidates(token, detected_catalog_numbers, seen, scores)

    for line in cleaned_lines:
        catalog_before_credit = _extract_catalog_before_credit_separator(line)
        if catalog_before_credit is not None:
            _append_catalog_number_candidates(catalog_before_credit, detected_catalog_numbers, seen, scores)
            continue

        slash_identity = _extract_slash_separated_identity(line)
        if slash_identity is not None:
            _append_catalog_number_candidates(slash_identity[0], detected_catalog_numbers, seen, scores)
            continue

        if _looks_like_copyright_year_line(line) and not _line_starts_with_catalog_token(line):
            continue

        if noisy_ocr_text:
            if _looks_like_standalone_compact_catalog_line(line):
                _append_catalog_number_candidates(line, detected_catalog_numbers, seen, scores)
            continue

        if _looks_like_numbered_track_listing(line):
            continue

        if _looks_like_credit_line(line):
            continue

        catalog_tokens = _extract_catalog_number_tokens(line)
        catalog_tokens = (*catalog_tokens, *_extract_ocr_confused_catalog_number_tokens(line))
        for token in catalog_tokens:
            _append_catalog_number_candidates(token, detected_catalog_numbers, seen, scores)

        if catalog_tokens and not _line_starts_with_catalog_token(line):
            continue

        if _looks_like_catalog_number(line):
            _append_catalog_number_candidates(line, detected_catalog_numbers, seen, scores)

    return tuple(_sort_catalog_number_candidates(detected_catalog_numbers, scores=scores))


def _extract_adjacent_catalog_number_tokens(cleaned_lines: list[str]) -> tuple[str, ...]:
    tokens: list[str] = []
    seen: set[str] = set()

    for index, line in enumerate(cleaned_lines[:-1]):
        next_line = cleaned_lines[index + 1]
        for token in _adjacent_catalog_number_token_variants(line, next_line):
            lowered_token = token.lower()
            if lowered_token in seen:
                continue
            seen.add(lowered_token)
            tokens.append(token)

    return tuple(tokens)


def _adjacent_catalog_number_token_variants(left: str, right: str) -> tuple[str, ...]:
    prefix = _clean_catalog_candidate(left)
    suffix = _clean_catalog_candidate(right)
    if prefix is None or suffix is None:
        return ()
    if not _looks_like_adjacent_catalog_prefix(prefix) or not _looks_like_adjacent_catalog_suffix(suffix):
        return ()

    compact_token = f"{prefix}{suffix}"
    spaced_token = f"{prefix} {suffix}"
    if not _looks_like_catalog_number(compact_token):
        return ()
    return compact_token, spaced_token


def _looks_like_adjacent_catalog_prefix(value: str) -> bool:
    tokens = TOKEN_PATTERN.findall(value)
    if len(tokens) != 1:
        return False

    token = tokens[0]
    lowered_value = value.lower()
    return (
        len(token) >= 2
        and token.upper() == token
        and any(character.isalpha() for character in token)
        and not any(character.isdigit() for character in token)
        and lowered_value not in NOISE_TERMS
        and not _is_side_heading(value)
        and not _looks_like_credit_line(value)
        and not _looks_like_legal_rights_line(value)
    )


def _looks_like_adjacent_catalog_suffix(value: str) -> bool:
    return re.fullmatch(r"\d{2,5}(?:LP|EP)?", value, re.IGNORECASE) is not None


def _catalog_source_lines(cleaned_lines: list[str], catalog_numbers: tuple[str, ...]) -> set[str]:
    if not catalog_numbers:
        return set()

    normalized_catalog_numbers = {_normalize_catalog_sort_token(value) for value in catalog_numbers}
    blocked_lines: set[str] = set()

    for line in cleaned_lines:
        normalized_line = _normalize_catalog_sort_token(line)
        if normalized_line in normalized_catalog_numbers:
            blocked_lines.add(line.lower())

    for index, line in enumerate(cleaned_lines[:-1]):
        next_line = cleaned_lines[index + 1]
        for token in _adjacent_catalog_number_token_variants(line, next_line):
            if _normalize_catalog_sort_token(token) not in normalized_catalog_numbers:
                continue
            blocked_lines.add(line.lower())
            blocked_lines.add(next_line.lower())
            break

    return blocked_lines


def _looks_like_noisy_ocr_text(cleaned_lines: list[str]) -> bool:
    if len(cleaned_lines) < 25:
        return False

    noisy_line_count = sum(1 for line in cleaned_lines if _looks_like_noisy_ocr_line(line))
    return noisy_line_count / len(cleaned_lines) >= 0.4


def _looks_like_noisy_ocr_line(line: str) -> bool:
    tokens = TOKEN_PATTERN.findall(line)
    alphanumeric_count = sum(character.isalnum() for character in line)
    if alphanumeric_count < 4:
        return True
    if not tokens:
        return True
    short_token_count = sum(len(token) <= 2 for token in tokens)
    if len(tokens) >= 3 and short_token_count * 2 >= len(tokens):
        return True
    punctuation_count = sum(not character.isalnum() and not character.isspace() for character in line)
    return punctuation_count > alphanumeric_count


def _looks_like_standalone_compact_catalog_line(line: str) -> bool:
    candidate = _clean_catalog_candidate(line)
    if candidate is None or " " in candidate:
        return False
    return _looks_like_catalog_number(candidate)


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

    top_stacked_pair = _select_top_stacked_artist_title(cleaned_lines, blocked_values=blocked_values)
    if top_stacked_pair is not None:
        return top_stacked_pair

    for line in cleaned_lines:
        if line.lower() in blocked_values:
            continue

        slash_identity = _extract_slash_separated_identity(line)
        if slash_identity is not None:
            _, artist, title = slash_identity
            return artist, title

    for line in cleaned_lines:
        if line.lower() in blocked_values:
            continue
        if _extract_track_listing_title(line) is not None:
            continue

        for separator in SEPARATOR_PATTERNS:
            if separator not in line:
                continue
            left, right = line.split(separator, maxsplit=1)
            artist = _clean_candidate_line(left)
            title = _clean_candidate_line(right)
            if artist and title and _is_strict_metadata_line(artist) and _is_strict_metadata_line(title):
                return artist, title

    candidate_entries = _candidate_metadata_entries(cleaned_lines, blocked_values=blocked_values)
    candidate_lines = [value for value, _ in candidate_entries]
    dj_pair = _select_dj_artist_title_pair(candidate_lines)
    if dj_pair is not None:
        return dj_pair

    uppercase_track_pair = _select_uppercase_artist_track_title_pair(candidate_entries)
    if uppercase_track_pair is not None:
        return uppercase_track_pair

    track_artist_pair = _select_nontrack_artist_with_track_title(candidate_entries)
    if track_artist_pair is not None:
        return track_artist_pair

    repeated_track_pair = _select_repeated_track_listing_artist_title(
        cleaned_lines,
        blocked_values=blocked_values,
    )
    if repeated_track_pair is not None:
        return repeated_track_pair

    title_first_credit_pair = _select_title_artist_before_credit_pair(
        cleaned_lines,
        blocked_values=blocked_values,
    )
    if title_first_credit_pair is not None:
        return title_first_credit_pair

    scored_pair = _select_artist_title_pair(candidate_entries)
    if scored_pair is not None:
        return scored_pair
    track_listing_title = _select_single_track_listing_title(candidate_entries)
    if track_listing_title is not None:
        return None, track_listing_title
    if len(candidate_lines) == 1 and _metadata_line_quality(candidate_lines[0]) > 0:
        return None, candidate_lines[0]

    return None, None


def _extract_slash_separated_identity(value: str) -> tuple[str, str, str] | None:
    parts = [part for part in re.split(r"\s*/+\s*", value.strip()) if part]
    if len(parts) < 3:
        return None

    catalog_number = _clean_catalog_candidate(parts[0])
    artist = _clean_candidate_line(parts[1])
    title = _clean_candidate_line(" / ".join(parts[2:]))
    if catalog_number is None or artist is None or title is None:
        return None
    if not _looks_like_catalog_number(catalog_number):
        return None
    if not (_is_strict_metadata_line(artist) and _is_strict_metadata_line(title)):
        return None

    return catalog_number, artist, title


def _extract_catalog_before_credit_separator(value: str) -> str | None:
    parts = [part.strip() for part in re.split(r"\s*[|/]+\s*", value.strip(), maxsplit=1)]
    if len(parts) != 2:
        return None

    catalog_candidate, credit_candidate = parts
    if not _looks_like_credit_line(credit_candidate):
        return None
    if _clean_catalog_candidate(catalog_candidate) is None:
        return None
    if not any(character.isdigit() for character in catalog_candidate):
        return None
    return catalog_candidate


def _select_top_stacked_artist_title(
    cleaned_lines: list[str],
    *,
    blocked_values: set[str],
) -> tuple[str, str] | None:
    first_side_index = next((index for index, line in enumerate(cleaned_lines) if _is_side_heading(line)), None)
    if first_side_index is None or first_side_index < 2:
        return None
    if first_side_index > 4:
        return None

    candidates: list[str] = []
    for line in cleaned_lines[:first_side_index]:
        if line.lower() in blocked_values:
            continue
        candidate = _clean_candidate_line(line)
        if candidate is None:
            continue
        if not _is_strict_metadata_line(candidate) and not _is_release_type_line(candidate):
            continue
        candidates.append(candidate)

    if len(candidates) < 2:
        return None
    if len(candidates) > 3:
        return None

    artist = candidates[0]
    title = candidates[1]
    if len(candidates) > 2 and _is_release_type_line(candidates[2]):
        title = f"{title} {candidates[2].upper()}"

    if not (_is_strict_metadata_line(artist) and _is_strict_metadata_line(title)):
        return None
    return artist, title


def _select_title_artist_before_credit_pair(
    cleaned_lines: list[str],
    *,
    blocked_values: set[str],
) -> tuple[str, str] | None:
    candidates: list[tuple[int, str]] = []
    for index, line in enumerate(cleaned_lines):
        if line.lower() in blocked_values:
            continue
        candidate = _clean_candidate_line(line)
        if candidate is None or not _is_candidate_metadata_line(candidate):
            continue
        candidates.append((index, candidate))

    for (title_index, title), (artist_index, artist) in zip(candidates, candidates[1:], strict=False):
        if artist_index != title_index + 1:
            continue
        if not _looks_like_title_first_line(title):
            continue
        if not _is_strict_metadata_line(artist):
            continue
        if not _has_credit_tail_after(cleaned_lines, artist_index):
            continue
        return artist, title

    return None


def _looks_like_title_first_line(value: str) -> bool:
    tokens = TOKEN_PATTERN.findall(value)
    if len(tokens) < 3:
        return False
    if any(any(character.isdigit() for character in token) for token in tokens):
        return False
    return _metadata_line_quality(value) >= 7


def _has_credit_tail_after(cleaned_lines: list[str], index: int) -> bool:
    return any(_looks_like_credit_line(line) for line in cleaned_lines[index + 1 : index + 4])


def _is_release_type_line(value: str) -> bool:
    return value.strip().upper() in {"EP", "LP"}


def _select_repeated_track_listing_title(cleaned_lines: list[str]) -> str | None:
    counts: dict[str, int] = {}
    values: dict[str, str] = {}
    for line in cleaned_lines:
        title = _extract_track_listing_title(line)
        if title is None:
            continue

        key = _normalize_catalog_sort_token(title)
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
        values.setdefault(key, title)

    repeated_titles = [values[key] for key, count in counts.items() if count >= 2]
    if len(repeated_titles) != 1:
        return None
    return repeated_titles[0]


def _select_single_track_listing_title(candidate_entries: list[tuple[str, bool]]) -> str | None:
    track_titles = [value for value, is_track in candidate_entries if is_track]
    if len(track_titles) != 1:
        return None
    return track_titles[0]


def _select_repeated_track_listing_artist_title(
    cleaned_lines: list[str],
    *,
    blocked_values: set[str],
) -> tuple[str | None, str] | None:
    title = _select_repeated_track_listing_title(cleaned_lines)
    if title is None:
        return None

    artist = _select_artist_before_track_listing(cleaned_lines, title=title, blocked_values=blocked_values)
    return artist, title


def _select_artist_before_track_listing(
    cleaned_lines: list[str],
    *,
    title: str,
    blocked_values: set[str],
) -> str | None:
    normalized_title = _normalize_catalog_sort_token(title)
    for index, line in enumerate(cleaned_lines):
        track_title = _extract_track_listing_title(line)
        if track_title is None or _normalize_catalog_sort_token(track_title) != normalized_title:
            continue

        for previous_line in reversed(cleaned_lines[:index]):
            if previous_line.lower() in blocked_values:
                continue
            candidate = _clean_candidate_line(previous_line)
            if candidate is None:
                continue
            if _normalize_catalog_sort_token(candidate) == normalized_title:
                continue
            if _is_strict_metadata_line(candidate) and _metadata_line_quality(candidate) > 0:
                return candidate
            if not _is_candidate_metadata_line(candidate):
                continue

        return None

    return None


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
        track_title = _extract_track_listing_title(line)
        if track_title is None:
            continue
        lowered_track_title = track_title.lower()
        if lowered_track_title in blocked_lines or not _is_candidate_metadata_line(track_title):
            continue
        fragments.append(track_title)
        blocked_lines.add(lowered_track_title)
        if len(fragments) == MAX_TEXT_FRAGMENTS:
            return tuple(fragments)

    for line in _candidate_metadata_lines(cleaned_lines, blocked_values=blocked_lines):
        lowered_line = line.lower()
        if lowered_line in blocked_lines or _looks_like_year_line(line):
            continue
        fragments.append(line)
        if len(fragments) == MAX_TEXT_FRAGMENTS:
            break

    return tuple(fragments)


def _candidate_metadata_lines(cleaned_lines: list[str], *, blocked_values: set[str]) -> list[str]:
    return [value for value, _ in _candidate_metadata_entries(cleaned_lines, blocked_values=blocked_values)]


def _candidate_metadata_entries(cleaned_lines: list[str], *, blocked_values: set[str]) -> list[tuple[str, bool]]:
    candidate_entries: list[tuple[str, bool]] = []
    seen: set[str] = set()
    previous_line_was_side_heading = False

    for line in cleaned_lines:
        lowered_line = line.lower()
        if lowered_line in blocked_values:
            previous_line_was_side_heading = False
            continue

        is_track_listing = previous_line_was_side_heading or _extract_track_listing_title(line) is not None
        candidate = _clean_candidate_line(line)
        previous_line_was_side_heading = _is_side_heading(line)
        if candidate is None or candidate.lower() in blocked_values:
            continue
        if candidate.lower() in seen or not _is_strict_metadata_line(candidate):
            continue

        seen.add(candidate.lower())
        candidate_entries.append((candidate, is_track_listing))

    return candidate_entries


def _looks_like_catalog_number(value: str) -> bool:
    cleaned_value = _clean_catalog_candidate(value)
    if cleaned_value is None:
        return False
    if len(cleaned_value) < 4 or len(cleaned_value) > 24:
        return False
    if _looks_like_track_listing(cleaned_value):
        return False
    if _looks_like_credit_line(cleaned_value) or _looks_like_company_year_catalog_noise(cleaned_value):
        return False
    if cleaned_value.isdigit():
        return False
    if _is_short_yearish_line(cleaned_value):
        return False
    if not any(character.isalpha() for character in cleaned_value):
        return False
    if not any(character.isdigit() for character in cleaned_value):
        return False
    if _looks_like_label_or_url_token(cleaned_value):
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
    if _looks_like_legal_rights_line(value):
        return False
    if _looks_like_track_listing(value):
        return False
    if _looks_like_side_marker_line(value):
        return False
    if _has_unbalanced_bracket_edge(value):
        return False
    if _looks_like_contact_or_url_line(value):
        return False
    if lowered_value.startswith(NOISE_PREFIXES):
        return False
    if _looks_like_credit_line(value):
        return False
    if _looks_like_year_line(value):
        return False
    if _is_labeled_metadata_line(value):
        return False
    if BARCODE_PATTERN.fullmatch(value.replace(" ", "")) is not None:
        return False
    alpha_tokens = [token for token in TOKEN_PATTERN.findall(value) if any(character.isalpha() for character in token)]
    if len(alpha_tokens) == 1 and alpha_tokens[0].islower() and len(alpha_tokens[0]) <= 4:
        return False
    if _looks_like_catalog_number(value):
        return False
    return any(character.isalpha() for character in value)


def _looks_like_credit_line(value: str) -> bool:
    normalized_value = _normalize_credit_line(value)
    lowered_value = f" {normalized_value} "
    if lowered_value.strip().endswith(" by"):
        return True
    if normalized_value.startswith(NOISE_PREFIXES):
        return True
    if normalized_value.startswith("for ") and " production" in lowered_value:
        return True
    return any(term in lowered_value for term in CREDIT_LINE_TERMS)


def _looks_like_side_marker_line(value: str) -> bool:
    return re.fullmatch(rf"\s*{SIDE_MARKER_PATTERN}[.)]?\s*side\s*", value, re.IGNORECASE) is not None


def _has_unbalanced_bracket_edge(value: str) -> bool:
    stripped_value = value.strip()
    opens_at_edge = stripped_value.startswith(("[", "("))
    closes_at_edge = stripped_value.endswith(("]", ")"))
    contains_open = any(character in stripped_value for character in "[(")
    contains_close = any(character in stripped_value for character in "])")
    return (opens_at_edge and not contains_close) or (closes_at_edge and not contains_open)


def _looks_like_legal_rights_line(value: str) -> bool:
    tokens = {token.lower() for token in TOKEN_PATTERN.findall(value)}
    if not tokens:
        return False

    if {"rights", "reserved"} <= tokens:
        return True
    if tokens & {"unauthorised", "unauthorized"}:
        return True
    if "broadcasting" in tokens and len(tokens) >= 3:
        return True

    return len(tokens & LEGAL_RIGHTS_TERMS) >= 2


def _looks_like_company_year_catalog_noise(value: str) -> bool:
    if _extract_year_from_value(value) is None:
        return False

    tokens = {token.lower() for token in TOKEN_PATTERN.findall(value)}
    return bool(tokens & {"music", "production", "productions", "records", "recordings", "copyright"})


def _looks_like_copyright_year_line(value: str) -> bool:
    if _extract_year_from_value(value) is None:
        return False
    return "©" in value or "℗" in value or re.search(r"\([cp]\)", value, re.IGNORECASE) is not None


def _normalize_credit_line(value: str) -> str:
    return " ".join(token.lower() for token in TOKEN_PATTERN.findall(value))


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
    if len(alpha_tokens[0]) == 1 and "&" in value:
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


def _select_artist_title_pair(candidate_entries: list[tuple[str, bool]]) -> tuple[str, str] | None:
    if len(candidate_entries) < 2:
        return None

    best_pair: tuple[str, str] | None = None
    best_score: float | None = None

    for index, ((artist, artist_is_track), (title, title_is_track)) in enumerate(
        zip(candidate_entries, candidate_entries[1:], strict=False)
    ):
        if artist_is_track and title_is_track:
            continue

        score = _metadata_line_quality(artist) + _metadata_line_quality(title) - min(index, 10) * 0.25
        if artist_is_track:
            score -= 8
        if title_is_track:
            score -= 3
        if best_score is None or score > best_score:
            best_score = score
            best_pair = (artist, title)

    if best_score is None or best_score < MIN_ARTIST_TITLE_PAIR_SCORE:
        return None
    return best_pair


def _select_dj_artist_title_pair(candidate_lines: list[str]) -> tuple[str, str] | None:
    dj_candidates: list[tuple[int, str]] = []
    for index, line in enumerate(candidate_lines):
        artist = _normalize_dj_artist_line(line)
        if artist is None:
            continue
        dj_candidates.append((index, artist))

    for index, artist in sorted(
        dj_candidates,
        key=lambda item: (-len(_normalize_catalog_sort_token(item[1])), item[0]),
    ):
        title = _select_dj_title_candidate(candidate_lines, artist_index=index)
        if title is not None:
            return artist, title

    return None


def _select_uppercase_artist_track_title_pair(candidate_entries: list[tuple[str, bool]]) -> tuple[str, str] | None:
    for index, ((artist, artist_is_track), (title, title_is_track)) in enumerate(
        zip(
            candidate_entries,
            candidate_entries[1:],
            strict=False,
        )
    ):
        if index > 0:
            return None
        if artist_is_track or not title_is_track:
            continue
        if not _looks_like_uppercase_artist_candidate(artist):
            continue
        return artist, title

    return None


def _select_nontrack_artist_with_track_title(candidate_entries: list[tuple[str, bool]]) -> tuple[str, str] | None:
    track_titles = [value for value, is_track in candidate_entries if is_track]
    if not track_titles:
        return None

    artist_candidates = [
        value
        for value, is_track in candidate_entries
        if not is_track and "&" in value and _metadata_line_quality(value) >= 6
    ]
    if not artist_candidates:
        return None

    return artist_candidates[-1], track_titles[0]


def _looks_like_uppercase_artist_candidate(value: str) -> bool:
    tokens = TOKEN_PATTERN.findall(value)
    alpha_tokens = [token for token in tokens if any(character.isalpha() for character in token)]
    return bool(alpha_tokens) and value.upper() == value and len(alpha_tokens) <= 4 and max(map(len, alpha_tokens)) >= 4


def _normalize_dj_artist_line(value: str) -> str | None:
    tokens = TOKEN_PATTERN.findall(value)
    if not tokens:
        return None

    normalized_value = " ".join(tokens)
    if normalized_value.lower().endswith(" presents"):
        normalized_value = normalized_value[: -len(" presents")].strip()

    compact_value = "".join(TOKEN_PATTERN.findall(normalized_value)).upper()
    if compact_value.startswith("DJ") and len(compact_value) > 2:
        return f"DJ {compact_value[2:]}".strip()

    return None


def _select_dj_title_candidate(candidate_lines: list[str], *, artist_index: int) -> str | None:
    following_candidates = candidate_lines[artist_index + 1 : artist_index + 5]
    for candidate in following_candidates:
        if _looks_like_dj_title_candidate(candidate):
            return candidate

    preceding_candidates = candidate_lines[max(0, artist_index - 4) : artist_index]
    for candidate in preceding_candidates:
        if _looks_like_dj_title_candidate(candidate):
            return candidate

    return None


def _looks_like_dj_title_candidate(value: str) -> bool:
    if _normalize_dj_artist_line(value) is not None:
        return False
    lowered_value = value.lower()
    if any(term in lowered_value for term in ("vinyl", "remaster", "side", "sound")):
        return False
    if _looks_like_credit_line(value) or _looks_like_track_listing(value):
        return False
    return _metadata_line_quality(value) > 0


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
        if not alpha_tokens[0].isupper():
            score -= 4

    return score


def _clean_candidate_line(value: str) -> str | None:
    cleaned_value = " ".join(value.strip(EDGE_JUNK_CHARACTERS).split())
    cleaned_value = _strip_track_listing_prefix(cleaned_value)
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
    cleaned_value = _strip_track_listing_prefix(cleaned_value)
    cleaned_value = _strip_catalog_side_suffix(cleaned_value)
    cleaned_value = " ".join(cleaned_value.strip(EDGE_JUNK_CHARACTERS).split())
    if " " not in cleaned_value and CATALOG_TOKEN_PATTERN.fullmatch(cleaned_value):
        cleaned_value = cleaned_value.upper()
    return cleaned_value or None


def _strip_catalog_side_suffix(value: str) -> str:
    return CATALOG_SIDE_SUFFIX_PATTERN.sub("", value).strip()


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
    scores: dict[str, int],
) -> None:
    for candidate in _catalog_number_variants(value):
        lowered_candidate = candidate.lower()
        scores[lowered_candidate] = scores.get(lowered_candidate, 0) + 1
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
    unwrapped_value = _unwrap_catalog_junk_token(normalized_value)

    for base_variant in (trimmed_value, normalized_value, unwrapped_value):
        if base_variant is None:
            continue

        candidate_variants = [base_variant]
        corrected_catalog = _correct_catalog_number_ocr(base_variant)
        if corrected_catalog is not None:
            candidate_variants.append(corrected_catalog)

        for candidate in tuple(candidate_variants):
            corrected_prefix = _correct_known_catalog_prefix_ocr(candidate)
            if corrected_prefix is not None:
                candidate_variants.append(corrected_prefix)

        for candidate in candidate_variants:
            if candidate is None:
                continue

            lowered_candidate = candidate.lower()
            if lowered_candidate in seen:
                continue
            seen.add(lowered_candidate)
            variants.append(candidate)

    return tuple(variants)


def _sort_catalog_number_candidates(candidates: list[str], *, scores: dict[str, int] | None = None) -> list[str]:
    normalized_candidates = [_normalize_catalog_sort_token(candidate) for candidate in candidates]
    scores = scores or {}

    def sort_key(indexed_candidate: tuple[int, str]) -> tuple[int, int, int, int]:
        index, candidate = indexed_candidate
        normalized_candidate = normalized_candidates[index]
        candidate_score = scores.get(candidate.lower(), 0)
        suffix_penalty = int(
            any(
                other
                and normalized_candidate.endswith(other)
                and len(normalized_candidate) > len(other)
                and candidate_score <= scores.get(candidates[other_index].lower(), 0)
                for other_index, other in enumerate(normalized_candidates)
            )
        )
        space_penalty = int(
            " " in candidate
            and SPACED_CATALOG_TOKEN_PATTERN.fullmatch(candidate) is None
            and LIMITED_EDITION_CATALOG_TOKEN_PATTERN.fullmatch(candidate) is None
        )
        frequency_score = scores.get(candidate.lower(), 0)
        return suffix_penalty, space_penalty, -frequency_score, index

    return [candidate for _, candidate in sorted(enumerate(candidates), key=sort_key)]


def _normalize_catalog_sort_token(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _extract_catalog_number_tokens(value: str) -> tuple[str, ...]:
    tokens: list[str] = []
    seen: set[str] = set()
    spaced_catalog_spans: list[tuple[int, int]] = []
    track_prefix_end = _track_listing_prefix_end(value)

    for match in LIMITED_EDITION_CATALOG_TOKEN_PATTERN.finditer(value):
        token = _clean_catalog_candidate(match.group(1))
        if token is None or token.lower() in seen:
            continue
        seen.add(token.lower())
        spaced_catalog_spans.append(match.span(1))
        tokens.append(token)

    for match in SPACED_CATALOG_TOKEN_PATTERN.finditer(value):
        if _is_span_inside_spaced_catalog(match.span(1), spaced_catalog_spans):
            continue
        if _catalog_span_is_inline_year_phrase(value, match.span(1)):
            continue
        if _catalog_span_is_track_title(value, match.span(1), track_prefix_end):
            continue
        if _catalog_span_is_duration_prefix(value, match.span(1)):
            continue
        token = _clean_catalog_candidate(match.group(1))
        if token is None or token.lower() in seen:
            continue
        if _extract_year_from_value(token) is not None or _looks_like_company_year_catalog_noise(token):
            continue
        seen.add(token.lower())
        spaced_catalog_spans.append(match.span(1))
        tokens.append(token)

    for match in SPACED_CONFUSED_CATALOG_TOKEN_PATTERN.finditer(value):
        if _is_span_inside_spaced_catalog(match.span(0), spaced_catalog_spans):
            continue
        if _catalog_span_is_inline_year_phrase(value, match.span(0)):
            continue
        if _catalog_span_is_track_title(value, match.span(0), track_prefix_end):
            continue
        if _catalog_span_is_duration_prefix(value, match.span(0)):
            continue
        token = _clean_catalog_candidate(f"{match.group(1)} {match.group(2)}")
        if token is None or token.lower() in seen:
            continue
        corrected_token = _correct_catalog_number_ocr(token)
        if corrected_token is None or not (
            _looks_like_catalog_number(corrected_token) or _looks_like_spaced_label_code_catalog_number(corrected_token)
        ):
            continue
        if _looks_like_company_year_catalog_noise(token) or _looks_like_company_year_catalog_noise(corrected_token):
            continue
        seen.add(token.lower())
        spaced_catalog_spans.append(match.span(0))
        tokens.append(token)

    for match in CATALOG_TOKEN_PATTERN.finditer(value):
        if track_prefix_end is not None and match.start(0) < track_prefix_end:
            continue
        if _is_span_inside_spaced_catalog(match.span(0), spaced_catalog_spans):
            continue
        token = _clean_catalog_candidate(_strip_leading_lowercase_ocr_prefix(match.group(0)))
        if token is None:
            continue
        token = token.upper()
        if (
            len(token) < 4
            or not any(character.isalpha() for character in token)
            or not any(character.isdigit() for character in token)
            or _looks_like_label_or_url_token(token)
            or token.lower() in seen
            or _looks_like_year_range_token(token)
        ):
            continue
        seen.add(token.lower())
        tokens.append(token)

    return tuple(tokens)


def _is_span_inside_spaced_catalog(span: tuple[int, int], spaced_catalog_spans: Iterable[tuple[int, int]]) -> bool:
    start, end = span
    return any(start >= spaced_start and end <= spaced_end for spaced_start, spaced_end in spaced_catalog_spans)


def _catalog_span_is_track_title(value: str, span: tuple[int, int], track_prefix_end: int | None) -> bool:
    if track_prefix_end is None or span[0] < track_prefix_end:
        return False
    if _has_rpm_marker_before_span(value, span, track_prefix_end):
        return False
    return _extract_track_listing_title(value) is not None


def _has_rpm_marker_before_span(value: str, span: tuple[int, int], track_prefix_end: int) -> bool:
    return re.search(r"\b\d{2}\s*rpm\b", value[track_prefix_end : span[0]], re.IGNORECASE) is not None


def _catalog_span_is_duration_prefix(value: str, span: tuple[int, int]) -> bool:
    _, end = span
    return value[end:].lstrip().startswith(":")


def _catalog_span_is_inline_year_phrase(value: str, span: tuple[int, int]) -> bool:
    start, end = span
    if start == 0 or not any(character.isalpha() for character in value[:start]):
        return False
    candidate = value[start:end].strip()
    return re.fullmatch(r"in\s+(?:19|20)\d{2}", candidate, re.IGNORECASE) is not None


def _looks_like_year_range_token(value: str) -> bool:
    return COPYRIGHT_YEAR_RANGE_PATTERN.fullmatch(value) is not None


def _extract_ocr_confused_catalog_number_tokens(value: str) -> tuple[str, ...]:
    tokens: list[str] = []
    seen: set[str] = set()
    track_prefix_end = _track_listing_prefix_end(value)

    for match in OCR_CONFUSED_CATALOG_TOKEN_PATTERN.finditer(value):
        if track_prefix_end is not None and match.start(1) < track_prefix_end:
            continue
        token = _clean_catalog_candidate(match.group(1))
        if token is None:
            continue

        corrected_token = _correct_catalog_number_ocr(token)
        if corrected_token is None or not _looks_like_catalog_number(corrected_token):
            continue

        lowered_token = token.lower()
        if lowered_token in seen:
            continue

        seen.add(lowered_token)
        tokens.append(token)

    for match in EDGE_CONFUSED_CATALOG_TOKEN_PATTERN.finditer(value):
        if track_prefix_end is not None and match.start(1) < track_prefix_end:
            continue
        token = _clean_catalog_candidate(match.group(1))
        if token is None:
            continue

        corrected_token = _correct_edge_confused_catalog_number(token)
        if corrected_token is None or not _looks_like_catalog_number(corrected_token):
            continue

        lowered_token = token.lower()
        if lowered_token in seen:
            continue

        seen.add(lowered_token)
        tokens.append(corrected_token)

    return tuple(tokens)


def _line_starts_with_catalog_token(value: str) -> bool:
    cleaned_value = _clean_catalog_candidate(value)
    if cleaned_value is None:
        return False

    first_token = cleaned_value.split()[0]
    return bool(CATALOG_TOKEN_PATTERN.fullmatch(first_token.upper()))


def _looks_like_spaced_label_code_catalog_number(value: str) -> bool:
    return re.fullmatch(r"[A-Z]{2,}\s+\d{2,6}(?:LP|EP)?", value, re.IGNORECASE) is not None


def _strip_leading_lowercase_ocr_prefix(value: str) -> str:
    if len(value) >= 2 and value[0].islower() and value[1].isupper():
        return value[1:]
    return value


def _strip_leading_lowercase_ocr_word(value: str) -> str:
    tokens = value.split()
    if len(tokens) >= 2 and len(tokens[0]) <= 2 and tokens[0].islower() and tokens[1][0].isupper():
        return " ".join(tokens[1:])
    return value


def _looks_like_track_listing(value: str) -> bool:
    if _extract_track_listing_title(value) is not None:
        return True

    tokens = TOKEN_PATTERN.findall(value)
    if len(tokens) >= 2 and tokens[0].isdigit() and all(token.isalpha() for token in tokens[1:]):
        return True

    return len(tokens) >= 3 and tokens[-1].isdigit() and all(token.isalpha() for token in tokens[:-1])


def _looks_like_numbered_track_listing(value: str) -> bool:
    return _extract_numbered_track_listing_title(value) is not None


def _is_side_heading(value: str) -> bool:
    return value.strip().lower() in {"this side", "that side", "other side"}


def _extract_track_listing_title(value: str) -> str | None:
    stripped_value = value.strip()
    match = TRACK_LISTING_PREFIX_PATTERN.match(stripped_value)
    if match is None:
        match = SIDE_PREFIX_PATTERN.match(stripped_value)
    if match is None:
        return _extract_numbered_track_listing_title(stripped_value)

    title = " ".join(stripped_value[match.end() :].strip(EDGE_JUNK_CHARACTERS).split())
    title = TRACK_SIDE_QUALIFIER_PATTERN.sub("", title)
    title = TRACK_SIDE_WORD_PREFIX_PATTERN.sub("", title)
    title = TRACK_DURATION_SUFFIX_PATTERN.sub("", title)
    title = _strip_numbered_track_suffix(title)
    title = " ".join(title.strip(EDGE_JUNK_CHARACTERS).split())
    if not title or not any(character.isalpha() for character in title):
        return None
    return title


def _extract_numbered_track_listing_title(value: str) -> str | None:
    stripped_value = value.strip()
    for pattern in (TRACK_LISTING_PREFIX_PATTERN, SIDE_PREFIX_PATTERN):
        match = pattern.match(stripped_value)
        if match is not None:
            stripped_value = stripped_value[match.end() :]
            break

    title = " ".join(stripped_value.strip(EDGE_JUNK_CHARACTERS).split())
    title = TRACK_SIDE_QUALIFIER_PATTERN.sub("", title)
    title = TRACK_SIDE_WORD_PREFIX_PATTERN.sub("", title)
    title = TRACK_DURATION_SUFFIX_PATTERN.sub("", title)
    stripped_title = _strip_numbered_track_suffix(title)
    if stripped_title == title:
        return None
    return stripped_title


def _strip_numbered_track_suffix(value: str) -> str:
    match = TRACK_NUMBER_SUFFIX_PATTERN.search(value)
    if match is None:
        return value

    title = " ".join(value[: match.start()].strip(EDGE_JUNK_CHARACTERS).split())
    title = _strip_leading_lowercase_ocr_word(title)
    if not _is_plausible_numbered_track_title(title, match.group(1)):
        return value
    return title


def _is_plausible_numbered_track_title(title: str, number: str) -> bool:
    title = _strip_leading_lowercase_ocr_prefix(title)
    tokens = TOKEN_PATTERN.findall(title)
    if not tokens:
        return False
    if all(len(token) <= 2 for token in tokens):
        return False
    if any(any(character.isdigit() for character in token) for token in tokens):
        return False
    if not all(any(character.isalpha() for character in token) for token in tokens):
        return False
    return number.startswith("0") or len(tokens) >= 3


def _track_listing_prefix_end(value: str) -> int | None:
    stripped_value = value.strip()
    match = TRACK_LISTING_PREFIX_PATTERN.match(stripped_value)
    if match is None:
        match = SIDE_PREFIX_PATTERN.match(stripped_value)
    if match is None:
        return None
    return match.end()


def _extract_track_listing_titles(cleaned_lines: list[str]) -> tuple[str, ...]:
    titles: list[str] = []
    seen: set[str] = set()
    for line in cleaned_lines:
        title = _extract_track_listing_title(line)
        if title is None:
            continue
        lowered_title = title.lower()
        if lowered_title in seen:
            continue
        seen.add(lowered_title)
        titles.append(title)
    return tuple(titles)


def _strip_track_listing_prefix(value: str) -> str:
    track_title = _extract_track_listing_title(value)
    if track_title is not None:
        return track_title
    return value


def _correct_catalog_number_ocr(value: str) -> str | None:
    corrected_suffix_value = _correct_catalog_suffix(value)
    if corrected_suffix_value is not None:
        return corrected_suffix_value

    corrected_characters: list[str] = []
    protected_release_type_start = _catalog_release_type_suffix_start(value)
    changed = False

    for index, character in enumerate(value):
        replacement = CATALOG_OCR_CORRECTIONS.get(character.lower()) or CATALOG_TERMINAL_OCR_CORRECTIONS.get(character)
        if (
            replacement is None
            or (protected_release_type_start is not None and index >= protected_release_type_start)
            or not _has_adjacent_digit(value, index)
        ):
            corrected_characters.append(character)
            continue

        corrected_characters.append(replacement)
        changed = True

    if not changed:
        return _correct_terminal_catalog_suffix(value)
    return "".join(corrected_characters)


def _correct_known_catalog_prefix_ocr(value: str) -> str | None:
    match = re.fullmatch(r"([A-Z]+)(\d{2,6}(?:LP|EP)?)", value, re.IGNORECASE)
    if match is None:
        return None

    prefix, suffix = match.groups()
    corrected_prefix = KNOWN_CATALOG_PREFIX_OCR_CORRECTIONS.get(prefix.upper())
    if corrected_prefix is None:
        return None
    return f"{corrected_prefix}{suffix.upper()}"


def _catalog_release_type_suffix_start(value: str) -> int | None:
    match = re.search(r"\d(?:LP|EP)$", value, re.IGNORECASE)
    if match is None:
        return None
    return len(value) - 2


def _correct_edge_confused_catalog_number(value: str) -> str | None:
    if len(value) < 5:
        return None

    first_replacement = CATALOG_EDGE_OCR_CORRECTIONS.get(value[0].lower())
    last_replacement = CATALOG_EDGE_OCR_CORRECTIONS.get(value[-1].lower())
    if first_replacement is None or last_replacement is None:
        return None

    middle = "".join(CATALOG_OCR_CORRECTIONS.get(character.lower(), character) for character in value[1:-1])
    corrected_value = f"{first_replacement}{middle}{last_replacement}"
    if sum(character.isdigit() for character in corrected_value) < 2:
        return None
    return corrected_value


def _correct_catalog_suffix(value: str) -> str | None:
    match = re.fullmatch(r"([A-Z]{2,}?)([ -]?)([OQDIL0-9]{2,6}?)(LP|EP)?", value, re.IGNORECASE)
    if match is None:
        return None

    prefix, separator, suffix, release_type = match.groups()
    if not any(character.isdigit() for character in suffix):
        return None

    corrected_suffix = "".join(CATALOG_OCR_CORRECTIONS.get(character.lower(), character) for character in suffix)
    corrected_value = f"{prefix.upper()}{separator}{corrected_suffix}{(release_type or '').upper()}"
    if corrected_value == value:
        return None
    return corrected_value


def _correct_terminal_catalog_suffix(value: str) -> str | None:
    if not value.endswith("?"):
        return None

    suffix_start = len(value)
    while suffix_start > 0 and value[suffix_start - 1].lower() in CATALOG_SUFFIX_OCR_CORRECTIONS:
        suffix_start -= 1

    prefix = value[:suffix_start]
    suffix = value[suffix_start:]
    if not (2 <= len(prefix) <= 8 and 2 <= len(suffix) <= 4):
        return None
    if not prefix.isalpha():
        return None

    corrected_suffix = "".join(CATALOG_SUFFIX_OCR_CORRECTIONS[character.lower()] for character in suffix)
    corrected_value = f"{prefix.upper()}{corrected_suffix}"
    if corrected_value == value:
        return None
    return corrected_value


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


def _unwrap_catalog_junk_token(value: str) -> str | None:
    if " " in value or not value.isalnum() or len(value) < 7:
        return None

    if not value[0].isalpha() or not value[-1].isalpha():
        return None

    inner_value = value[1:-1]
    if not any(character.isdigit() for character in inner_value):
        return None

    corrected_inner_value = _correct_catalog_number_ocr(inner_value) or inner_value
    if not re.fullmatch(r"[A-Z]{2,}\d{3,}(?:LP|EP)?", corrected_inner_value, re.IGNORECASE):
        return None

    return corrected_inner_value.upper()


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


def _looks_like_label_or_url_token(value: str) -> bool:
    lowered_parts = [part.lower() for part in re.split(r"[-/.#\s]+", value) if part]
    if not lowered_parts:
        return False
    if any(part in {"com", "net", "org", "www", "myspace", "gmail"} for part in lowered_parts):
        return True
    return any(part in LABEL_SUFFIX_TERMS for part in lowered_parts)


def _looks_like_contact_or_url_line(value: str) -> bool:
    return EMAIL_ADDRESS_PATTERN.search(value) is not None or URL_TEXT_PATTERN.search(value) is not None


def _looks_like_contact_number_line(value: str) -> bool:
    if BARCODE_CONTEXT_PATTERN.search(value):
        return False
    return CONTACT_NUMBER_CONTEXT_PATTERN.search(value) is not None


def _is_valid_ocr_barcode_candidate(barcode: str, *, line: str, checksum_valid: bool) -> bool:
    if not (8 <= len(barcode) <= 14):
        return False
    if checksum_valid:
        return True
    if len(barcode) in GTIN_CHECKSUM_LENGTHS:
        return is_valid_gtin(barcode)
    if BARCODE_CONTEXT_PATTERN.search(line):
        return True
    return not _looks_like_contact_number_line(line)


def _has_valid_upc_ean_checksum(value: str) -> bool:
    if len(value) == 12:
        return _has_valid_gtin_checksum(f"0{value}")
    if len(value) == 13:
        return _has_valid_gtin_checksum(value)
    return False


def _has_valid_gtin_checksum(value: str) -> bool:
    digits = [int(character) for character in value]
    check_digit = digits[-1]
    body = digits[:-1]
    total = sum(digit if index % 2 == 0 else digit * 3 for index, digit in enumerate(body))
    return (10 - (total % 10)) % 10 == check_digit


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
    if (
        _looks_like_catalog_number(value)
        or _looks_like_year_line(value)
        or _looks_like_credit_line(value)
        or _is_labeled_metadata_line(value)
    ):
        return False
    if any(lowered_value == suffix or lowered_value.endswith(f" {suffix}") for suffix in LABEL_SUFFIX_TERMS):
        return True

    tokens = {token.lower() for token in TOKEN_PATTERN.findall(value)}
    return bool(tokens & LABEL_INFIX_TERMS)


def _is_short_yearish_line(value: str) -> bool:
    if _extract_year_from_value(value) is None:
        return False

    value_without_year = YEAR_PATTERN.sub("", value.lower())
    alpha_count = sum(character.isalpha() for character in value_without_year)
    return alpha_count <= 2
