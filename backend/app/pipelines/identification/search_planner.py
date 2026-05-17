import re
from dataclasses import dataclass

from app.pipelines.identification.models import ExtractedIdentifiers, IdentifierEvidence, IdentifyCandidate
from app.pipelines.identification.search_evidence import score_search_evidence

DEFAULT_MAX_RAW_CONTEXT_SEARCHES = 8
DEFAULT_CATALOG_CONTEXT_LIMIT = 4
DEFAULT_PHRASE_CONTEXT_LIMIT = 5
DEFAULT_ROLE_CONTEXT_CATALOG_LIMIT = 1
DEFAULT_ROLE_CONTEXT_LABEL_LIMIT = 2
DEFAULT_IDENTITY_CONTEXT_LIMIT = 6
DEFAULT_TITLE_CONTEXT_LIMIT = 6
DEFAULT_TRACKLIST_QUERY_LIMIT = 6
DEFAULT_TRACKLIST_TRACK_LIMIT = 8
STRONG_PADDLEOCR_EVIDENCE_MIN_CONFIDENCE = 0.85
QUERY_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9#./-]+")
CREDIT_PREFIXES = (
    "all tracks",
    "additional production",
    "production",
    "mastered",
    "mixed",
    "produced",
    "written",
    "published",
    "copyright",
    "manufactured",
    "distributed",
    "licenced",
    "licensed",
    "a r",
)
CREDIT_QUERY_TERMS = (
    " written ",
    " produced ",
    " produc ",
    " production ",
    " productions ",
    " mastered ",
    " mixed ",
    " engineered ",
    " manufactured ",
    " distributed ",
    " licenced ",
    " licensed ",
)
LOW_VALUE_QUERY_LINES = {
    "45 rpm",
    "33 rpm",
    "rpm",
    "this side",
    "other side",
    "side a",
    "side b",
    "limited edition",
}
SIDE_MARKER_PATTERN = r"(?:[A-H]{1,2}|[A-H](?:\d{1,2}|[IL]{1,3}|IV|V))"
TRACK_QUERY_PREFIX_PATTERN = re.compile(rf"^{SIDE_MARKER_PATTERN}[.)]?\s+", re.IGNORECASE)
TRACK_QUERY_DOTTED_PREFIX_PATTERN = re.compile(
    rf"^{SIDE_MARKER_PATTERN}\s*[.),]\s*(?=[A-Za-z0-9])",
    re.IGNORECASE,
)
SIDE_QUALIFIER_PREFIXES = ("there ", "here ")


@dataclass(frozen=True)
class SearchStep:
    strategy: str
    params: dict[str, str]


def build_search_plan(identifiers: ExtractedIdentifiers) -> list[SearchStep]:
    search_steps: list[SearchStep] = []

    for barcode in identifiers.barcodes:
        search_steps.append(SearchStep(strategy="barcode", params={"barcode": barcode}))

    for catalog_number in identifiers.catalog_numbers:
        search_steps.append(SearchStep(strategy="catalog_number", params={"catalog_number": catalog_number}))

    for query in _build_catalog_identity_context_queries(identifiers):
        search_steps.append(SearchStep(strategy="catalog_identity_context", params={"query": query}))

    for query in _build_vlm_discogs_queries(identifiers):
        search_steps.append(SearchStep(strategy="vlm_discogs_query", params={"query": query}))

    ocr_role_context_queries = _build_ocr_role_context_queries(identifiers)
    for query in ocr_role_context_queries:
        search_steps.append(SearchStep(strategy="ocr_role_context", params={"query": query}))

    title_context_queries: tuple[str, ...] = ()
    should_defer_title_context = False
    if not identifiers.artist:
        title_context_queries = _build_title_context_queries(identifiers)
        should_defer_title_context = bool(identifiers.catalog_numbers) or _has_raw_catalog_context(identifiers)
        if not should_defer_title_context:
            for query in title_context_queries:
                search_steps.append(SearchStep(strategy="title_context", params={"query": query}))

    identity_context_queries: tuple[str, ...] = ()
    has_plausible_identity = _has_plausible_identity(identifiers)
    if identifiers.artist and identifiers.title and not ocr_role_context_queries and has_plausible_identity:
        search_steps.append(
            SearchStep(
                strategy="artist_title",
                params={"artist": identifiers.artist, "title": identifiers.title},
            )
        )
        identity_context_queries = _build_identity_context_queries(identifiers)
        for query in identity_context_queries:
            search_steps.append(SearchStep(strategy="identity_context", params={"query": query}))

    should_run_loose_text_searches = (
        not identity_context_queries or bool(identifiers.catalog_numbers)
    ) and not _has_strong_paddleocr_identity_evidence(identifiers)
    if not ocr_role_context_queries and should_run_loose_text_searches:
        for query in _build_tracklist_context_queries(identifiers):
            search_steps.append(SearchStep(strategy="tracklist_context", params={"query": query}))

        for query in _build_raw_context_queries(identifiers):
            search_steps.append(SearchStep(strategy="raw_context", params={"query": query}))

        for fragment in identifiers.text_fragments:
            for query in _free_text_fragment_queries(fragment):
                search_steps.append(SearchStep(strategy="free_text", params={"query": query}))

    if should_defer_title_context:
        for query in title_context_queries:
            search_steps.append(SearchStep(strategy="title_context", params={"query": query}))

    return _dedupe_search_steps(search_steps)


def candidates_contain_identity_context(
    candidates: list[IdentifyCandidate] | tuple[IdentifyCandidate, ...],
    identifiers: ExtractedIdentifiers,
) -> bool:
    if not identifiers.artist or not identifiers.title:
        return False

    normalized_artist = _normalize_query_key(identifiers.artist)
    normalized_title = _normalize_query_key(identifiers.title)
    if not normalized_artist or not normalized_title:
        return False

    for candidate in candidates:
        candidate_key = _normalize_query_key(
            " ".join(
                value
                for value in (
                    candidate.artist,
                    candidate.title,
                    candidate.label,
                    candidate.catalog_number,
                )
                if value
            )
        )
        if normalized_artist in candidate_key and normalized_title in candidate_key:
            return True

    return False


def _dedupe_search_steps(search_steps: list[SearchStep]) -> list[SearchStep]:
    deduped_steps: list[SearchStep] = []
    seen: set[tuple[str, tuple[tuple[str, str], ...]]] = set()

    for search_step in search_steps:
        key = (search_step.strategy, tuple(sorted(search_step.params.items())))
        if key in seen:
            continue
        seen.add(key)
        deduped_steps.append(search_step)

    return deduped_steps


def _has_strong_paddleocr_identity_evidence(identifiers: ExtractedIdentifiers) -> bool:
    return any(_is_strong_paddleocr_identity_evidence(evidence) for evidence in identifiers.identifier_evidence)


def _is_strong_paddleocr_identity_evidence(evidence: IdentifierEvidence) -> bool:
    return (
        evidence.source == "paddleocr_vl"
        and evidence.kind in {"catalog_number", "artist", "title", "label", "text_fragment"}
        and evidence.confidence is not None
        and evidence.confidence >= STRONG_PADDLEOCR_EVIDENCE_MIN_CONFIDENCE
    )


def _build_ocr_role_context_queries(identifiers: ExtractedIdentifiers) -> tuple[str, ...]:
    if not identifiers.catalog_numbers or not identifiers.ocr_roles:
        return ()

    title_values = _role_texts(identifiers, "release_title")
    label_values = _role_texts(identifiers, "label")
    if not title_values and not label_values:
        return ()

    queries: list[str] = []
    catalog_numbers = _rank_catalog_context_values(identifiers.catalog_numbers)
    for catalog_number in catalog_numbers[:DEFAULT_ROLE_CONTEXT_CATALOG_LIMIT]:
        for title in title_values[:DEFAULT_PHRASE_CONTEXT_LIMIT]:
            queries.append(f"{catalog_number} {title}")
        for label in label_values[:DEFAULT_ROLE_CONTEXT_LABEL_LIMIT]:
            queries.append(f"{catalog_number} {label}")

    return tuple(_dedupe_strings(queries)[:DEFAULT_MAX_RAW_CONTEXT_SEARCHES])


def _build_catalog_identity_context_queries(identifiers: ExtractedIdentifiers) -> tuple[str, ...]:
    catalog_numbers = _catalog_spacing_variant_values(identifiers.catalog_numbers)
    if not catalog_numbers:
        return ()

    identity_values = [
        value
        for value in (identifiers.artist, identifiers.label)
        if value and not _looks_like_credit_query(value) and not _is_low_value_query_line(value)
    ]
    if not identity_values:
        return ()

    queries: list[str] = []
    for catalog_number in catalog_numbers[:DEFAULT_ROLE_CONTEXT_CATALOG_LIMIT]:
        for value in identity_values[:DEFAULT_ROLE_CONTEXT_LABEL_LIMIT]:
            if _normalize_query_key(catalog_number) == _normalize_query_key(value):
                continue
            queries.append(f"{catalog_number} {value}")

    return tuple(_dedupe_strings(queries)[:DEFAULT_MAX_RAW_CONTEXT_SEARCHES])


def _build_title_context_queries(identifiers: ExtractedIdentifiers) -> tuple[str, ...]:
    if not identifiers.title:
        return ()

    raw_lines = [
        line
        for line in _extract_raw_search_lines(identifiers.raw_text)
        if not _looks_like_catalog_query_line(line)
        and not _looks_like_credit_query(line)
        and not _is_low_value_query_line(line)
        and _looks_like_context_phrase(line)
    ]
    context_values = [
        *_role_texts(identifiers, "release_title"),
        *identifiers.text_fragments,
        *raw_lines,
    ]

    title_values = _title_context_values(identifiers)
    phrase_values = _dedupe_strings(
        [
            line
            for value in context_values
            if (line := _clean_query_line(value)) is not None
            and _looks_like_context_phrase(line)
            and not _looks_like_title_variant(line, identifiers.title)
        ]
    )

    queries: list[str] = []
    for title in title_values[:2]:
        for phrase in phrase_values[:DEFAULT_PHRASE_CONTEXT_LIMIT]:
            queries.append(f"{title} {phrase}")

    return tuple(_dedupe_strings(queries)[:DEFAULT_TITLE_CONTEXT_LIMIT])


def _has_raw_catalog_context(identifiers: ExtractedIdentifiers) -> bool:
    return any(_looks_like_catalog_query_line(line) for line in _extract_raw_search_lines(identifiers.raw_text))


def _title_context_values(identifiers: ExtractedIdentifiers) -> list[str]:
    if identifiers.title is None:
        return []

    values = [identifiers.title]
    compact_title = _compact_spaced_track_title(identifiers.title, raw_text=identifiers.raw_text)
    if compact_title is not None:
        values.insert(0, compact_title)

    return _dedupe_strings(values)


def _compact_spaced_track_title(title: str, *, raw_text: str) -> str | None:
    tokens = title.split()
    if len(tokens) != 2:
        return None
    if not all(token.isalpha() and token.upper() == token and len(token) >= 3 for token in tokens):
        return None

    title_pattern = r"\s+".join(re.escape(token) for token in tokens)
    if re.search(rf"\b{title_pattern}\b\s+\d{{1,2}}:\d{{2}}(?::\d{{2}})?", raw_text) is None:
        return None

    if tokens[0].endswith(tokens[1][0]):
        return f"{tokens[0][:-1]}{tokens[1]}"
    return "".join(tokens)


def _catalog_spacing_variant_values(catalog_numbers: tuple[str, ...]) -> list[str]:
    normalized_counts: dict[str, int] = {}
    for catalog_number in catalog_numbers:
        normalized_value = _normalize_query_key(catalog_number)
        normalized_counts[normalized_value] = normalized_counts.get(normalized_value, 0) + 1

    return [
        catalog_number
        for catalog_number in _rank_catalog_context_values(catalog_numbers)
        if normalized_counts.get(_normalize_query_key(catalog_number), 0) > 1
    ]


def _build_identity_context_queries(identifiers: ExtractedIdentifiers) -> tuple[str, ...]:
    if not identifiers.artist or not identifiers.title:
        return ()

    raw_lines = [
        line
        for line in _extract_raw_search_lines(identifiers.raw_text)
        if not _looks_like_catalog_query_line(line)
        and not _contains_catalog_value(line, identifiers.catalog_numbers)
        and not _looks_like_credit_query(line)
        and not _is_low_value_query_line(line)
    ]
    values = [identifiers.artist, identifiers.title, *identifiers.text_fragments, *raw_lines]
    artist_values = _rank_artist_identity_values(
        [value for value in values if _looks_like_artist_variant(value, identifiers.artist)],
        identifiers.artist,
    )
    title_values = _rank_title_identity_values(_identity_title_values(values, identifiers.title), identifiers.title)
    supporting_fragments = _identity_supporting_fragments(
        identifiers.text_fragments,
        artist=identifiers.artist,
        title=identifiers.title,
    )

    queries: list[str] = []
    for artist in artist_values[:3]:
        for title in title_values[:3]:
            if _normalize_query_key(artist) == _normalize_query_key(title):
                continue
            queries.append(f"{artist} {title}")
            for fragment in supporting_fragments[:2]:
                queries.append(f"{artist} {title} {fragment}")
                queries.append(f"{title} {fragment}")

    return tuple(_dedupe_strings(queries)[:DEFAULT_IDENTITY_CONTEXT_LIMIT])


def _has_plausible_identity(identifiers: ExtractedIdentifiers) -> bool:
    if not identifiers.artist or not identifiers.title:
        return False
    return not (
        _looks_like_credit_query(identifiers.artist)
        or _looks_like_credit_query(identifiers.title)
        or _is_low_value_query_line(identifiers.artist)
        or _is_low_value_query_line(identifiers.title)
    )


def _looks_like_credit_query(value: str) -> bool:
    lowered_value = _normalize_credit_query(value)
    stripped_value = lowered_value.strip()
    if stripped_value.startswith(CREDIT_PREFIXES):
        return True
    if stripped_value.endswith(" by"):
        return True
    if stripped_value.startswith("for ") and " production" in f" {lowered_value} ":
        return True
    return any(term in f" {lowered_value} " for term in CREDIT_QUERY_TERMS)


def _normalize_credit_query(value: str) -> str:
    return " ".join(token.lower() for token in QUERY_TOKEN_PATTERN.findall(value))


def _rank_identity_values(values: list[str]) -> list[str]:
    return sorted(_dedupe_strings(values), key=lambda value: (-len(_normalize_query_key(value)), value))


def _rank_artist_identity_values(values: list[str], artist: str) -> list[str]:
    normalized_artist = _normalize_query_key(artist)
    return sorted(
        _dedupe_strings(values),
        key=lambda value: (
            _normalize_query_key(value) != normalized_artist,
            -len(_normalize_query_key(value)),
            value,
        ),
    )


def _rank_title_identity_values(values: list[str], title: str) -> list[str]:
    normalized_title = _normalize_query_key(title)
    return sorted(
        _dedupe_strings(values),
        key=lambda value: (
            _normalize_query_key(value) != normalized_title,
            -len(_normalize_query_key(value)),
            value,
        ),
    )


def _contains_catalog_value(value: str, catalog_numbers: tuple[str, ...]) -> bool:
    normalized_value = _normalize_query_key(value)
    return any(_normalize_query_key(catalog_number) in normalized_value for catalog_number in catalog_numbers)


def _identity_title_values(values: list[str | None], title: str) -> list[str]:
    release_type = _extract_release_type_hint(values)
    title_values: list[str] = []
    for value in values:
        if not _looks_like_title_variant(value, title):
            continue
        title_values.extend(_title_search_variants(value, release_type=release_type))
    return title_values


def _identity_supporting_fragments(
    values: tuple[str, ...],
    *,
    artist: str,
    title: str,
) -> list[str]:
    fragments: list[str] = []
    for value in values:
        line = _clean_query_line(value)
        if line is None:
            continue
        if _looks_like_credit_query(line) or _looks_like_catalog_query_line(line) or _is_low_value_query_line(line):
            continue
        if _looks_like_artist_variant(line, artist) or _looks_like_title_variant(line, title):
            continue
        if not _looks_like_identity_supporting_fragment(line):
            continue
        fragments.append(line)

    return _rank_identity_values(fragments)


def _looks_like_identity_supporting_fragment(value: str) -> bool:
    tokens = QUERY_TOKEN_PATTERN.findall(value)
    if not (1 <= len(tokens) <= 3):
        return False
    if any(token.isdigit() for token in tokens):
        return False
    if len(tokens) == 1:
        token = tokens[0]
        return len(token) >= 5 and token.upper() == token
    return score_search_evidence(value).score >= 2


def _title_search_variants(value: str | None, *, release_type: str | None) -> tuple[str, ...]:
    line = _clean_query_line(value or "")
    if line is None:
        return ()

    variants = [line]
    tokens = line.split()
    if tokens and _release_type_from_token(tokens[-1]) is not None:
        tokens[-1] = _release_type_from_token(tokens[-1]) or tokens[-1]
        variants.append(" ".join(tokens))

    if len(tokens) == 1 and len(tokens[0]) >= 5 and tokens[0].isupper() and not tokens[0].lower().endswith("y"):
        variants.append(f"{tokens[0]}Y")

    if release_type is not None and all(token.upper() not in {"EP", "LP"} for token in tokens):
        variants.extend(f"{variant} {release_type}" for variant in tuple(variants))

    return tuple(_dedupe_strings(variants))


def _extract_release_type_hint(values: list[str | None]) -> str | None:
    for value in values:
        tokens = QUERY_TOKEN_PATTERN.findall(value or "")
        if not tokens:
            continue

        release_type = _release_type_from_token(tokens[-1])
        if release_type is not None:
            return release_type

    return None


def _release_type_from_token(value: str) -> str | None:
    normalized_value = value.upper()
    if normalized_value in {"EP", "LP"}:
        return normalized_value
    if normalized_value in {"FE", "EF", "EIP"}:
        return "EP"
    return None


def _looks_like_artist_variant(value: str | None, artist: str) -> bool:
    if value is None:
        return False

    normalized_artist = _normalize_query_key(artist)
    normalized_value = _normalize_query_key(value)
    if not normalized_artist or not normalized_value:
        return False
    if normalized_value.startswith("dj") and normalized_artist.startswith("dj"):
        return True
    return normalized_artist in normalized_value or normalized_value in normalized_artist


def _looks_like_title_variant(value: str | None, title: str) -> bool:
    if value is None:
        return False

    normalized_title = _normalize_query_key(title)
    normalized_value = _normalize_query_key(value)
    if len(normalized_title) < 4 or len(normalized_value) < 4:
        return False
    if normalized_title in normalized_value or normalized_value in normalized_title:
        return True
    return _common_prefix_length(normalized_title, normalized_value) >= 3


def _common_prefix_length(left: str, right: str) -> int:
    count = 0
    for left_character, right_character in zip(left, right, strict=False):
        if left_character != right_character:
            break
        count += 1
    return count


def _role_texts(identifiers: ExtractedIdentifiers, role: str) -> list[str]:
    return _dedupe_strings([evidence.text for evidence in identifiers.ocr_roles if evidence.role == role])


def _rank_catalog_context_values(catalog_numbers: tuple[str, ...]) -> list[str]:
    return sorted(catalog_numbers, key=_catalog_context_sort_key)


def _catalog_context_sort_key(value: str) -> tuple[int, int, int, str]:
    digit_count = sum(character.isdigit() for character in value)
    suspicious_count = sum(character in "?|" for character in value)
    return suspicious_count, -digit_count, len(value), value


def _build_raw_context_queries(identifiers: ExtractedIdentifiers) -> tuple[str, ...]:
    if not identifiers.raw_text.strip():
        return ()

    raw_lines = _extract_raw_search_lines(identifiers.raw_text)
    if not raw_lines:
        return ()

    catalog_lines = _dedupe_strings(
        [
            *identifiers.catalog_numbers,
            *(
                line
                for line in raw_lines
                if _looks_like_catalog_query_line(line) and not _looks_like_slash_identity_query_line(line)
            ),
        ]
    )
    phrase_lines = _dedupe_strings(
        [line for line in raw_lines if not _looks_like_catalog_query_line(line) and _looks_like_context_phrase(line)]
    )

    queries: list[str] = []
    for catalog_line in catalog_lines[:DEFAULT_CATALOG_CONTEXT_LIMIT]:
        for phrase in phrase_lines[:DEFAULT_PHRASE_CONTEXT_LIMIT]:
            if _normalize_query_key(catalog_line) == _normalize_query_key(phrase):
                continue
            queries.append(f"{catalog_line} {phrase}")

    for left, right in zip(phrase_lines, phrase_lines[1:], strict=False):
        queries.append(f"{left} {right}")

    queries.extend(phrase_lines[:DEFAULT_PHRASE_CONTEXT_LIMIT])
    return tuple(_dedupe_strings(queries)[:DEFAULT_MAX_RAW_CONTEXT_SEARCHES])


def _build_tracklist_context_queries(identifiers: ExtractedIdentifiers) -> tuple[str, ...]:
    if identifiers.artist or identifiers.title or identifiers.catalog_numbers or len(identifiers.text_fragments) < 2:
        return ()

    track_titles = _tracklist_query_fragments(identifiers.text_fragments)
    if len(track_titles) < 2:
        return ()

    queries: list[str] = []
    artist_hints = _short_uppercase_context_values(identifiers.raw_text)
    combined_tracks = " ".join(track_titles[:DEFAULT_TRACKLIST_TRACK_LIMIT])
    shorter_combined_tracks = " ".join(track_titles[: max(2, min(len(track_titles) - 1, 4))])

    for artist_hint in artist_hints[:2]:
        queries.append(f"{artist_hint} {combined_tracks}")
        if shorter_combined_tracks != combined_tracks:
            queries.append(f"{artist_hint} {shorter_combined_tracks}")

    queries.append(combined_tracks)
    if shorter_combined_tracks != combined_tracks:
        queries.append(shorter_combined_tracks)

    for left, right in zip(track_titles, track_titles[1:], strict=False):
        queries.append(f"{left} {right}")

    return tuple(_dedupe_strings(queries)[:DEFAULT_TRACKLIST_QUERY_LIMIT])


def _tracklist_query_fragments(values: tuple[str, ...]) -> list[str]:
    fragments: list[str] = []
    for value in values:
        line = _clean_query_line(value)
        if line is None or _looks_like_credit_query(line) or _looks_like_catalog_query_line(line):
            continue

        tokens = QUERY_TOKEN_PATTERN.findall(line)
        if not (1 <= len(tokens) <= 4):
            continue
        if any(token.isdigit() for token in tokens):
            continue
        if all(len(token) <= 2 for token in tokens):
            continue
        fragments.append(line)

    return _dedupe_strings(fragments)


def _short_uppercase_context_values(raw_text: str) -> list[str]:
    values: list[str] = []
    for raw_line in raw_text.splitlines():
        line = _clean_query_line(raw_line)
        if line is None:
            continue
        tokens = QUERY_TOKEN_PATTERN.findall(line)
        if len(tokens) != 1:
            continue

        token = tokens[0]
        if 2 <= len(token) <= 4 and token.upper() == token and any(character.isalpha() for character in token):
            values.append(token)

    return _dedupe_strings(values)


def _build_vlm_discogs_queries(identifiers: ExtractedIdentifiers) -> tuple[str, ...]:
    queries: list[str] = []
    for raw_line in identifiers.raw_text.splitlines():
        if not raw_line.lower().startswith("discogs query:"):
            continue
        query = _clean_query_line(raw_line.split(":", maxsplit=1)[1])
        if query is not None and _has_query_value(query):
            queries.append(query)
    return tuple(_dedupe_strings(queries)[:3])


def _extract_raw_search_lines(raw_text: str) -> list[str]:
    lines: list[str] = []

    for raw_line in raw_text.splitlines():
        if _has_unbalanced_bracket_edge(raw_line):
            continue

        line = _clean_query_line(raw_line)
        if line is not None and _has_query_value(line):
            lines.append(line)

        for credit_name in _extract_credit_name_queries(raw_line):
            if _has_query_value(credit_name):
                lines.append(credit_name)

    return _dedupe_strings(lines)


def _clean_query_line(value: str) -> str | None:
    tokens = QUERY_TOKEN_PATTERN.findall(value)
    if not tokens:
        return None

    line = " ".join(tokens).strip(" -./#")
    line = _strip_track_query_prefix(line)
    line = _strip_numeric_track_query_prefix(line)
    lowered_line = line.lower()
    for prefix in SIDE_QUALIFIER_PREFIXES:
        if lowered_line.startswith(prefix) and len(line.split()) > 1:
            line = line[len(prefix) :].strip()
            lowered_line = line.lower()
    normalized_line = " ".join(line.split())
    return normalized_line or None


def _has_query_value(line: str) -> bool:
    if _is_low_value_query_line(line):
        return False
    if _looks_like_credit_query(line):
        return False

    alphanumeric_count = sum(character.isalnum() for character in line)
    return alphanumeric_count >= 4


def _is_low_value_query_line(line: str) -> bool:
    return _normalize_credit_query(line) in LOW_VALUE_QUERY_LINES


def _strip_numeric_track_query_prefix(line: str) -> str:
    tokens = line.split()
    if len(tokens) < 2 or not tokens[0].isdigit():
        return line

    prefix = int(tokens[0])
    if prefix > 12 and prefix not in {81, 82, 83, 84, 85, 86, 87, 88}:
        return line
    if not any(character.isalpha() for character in tokens[1]):
        return line
    return " ".join(tokens[1:])


def _should_search_free_text_fragment(fragment: str) -> bool:
    line = _clean_query_line(fragment)
    if line is None or not _has_query_value(line):
        return False
    if not _looks_like_context_phrase(line):
        return False
    return score_search_evidence(line).is_query_worthy


def _free_text_fragment_queries(fragment: str) -> tuple[str, ...]:
    line = _clean_query_line(fragment)
    if line is None or not _should_search_free_text_fragment(line):
        return ()

    return (line,)


def _has_unbalanced_bracket_edge(value: str) -> bool:
    stripped_value = value.strip()
    opens_at_edge = stripped_value.startswith(("[", "("))
    closes_at_edge = stripped_value.endswith(("]", ")"))
    contains_open = any(character in stripped_value for character in "[(")
    contains_close = any(character in stripped_value for character in "])")
    return (opens_at_edge and not contains_close) or (closes_at_edge and not contains_open)


def _extract_credit_name_queries(value: str) -> tuple[str, ...]:
    line = _clean_query_line(value)
    if line is None or " by " not in f" {line.lower()} ":
        return ()

    lowered_line = line.lower()
    if lowered_line.startswith("by "):
        original_credit_value = line[len("by ") :]
    else:
        return ()

    names = re.split(r"\s+(?:and|&|x)\s+|,", original_credit_value)

    queries: list[str] = []
    for name in names:
        cleaned_name = _clean_query_line(name)
        if cleaned_name is None or _looks_like_credit_query(cleaned_name):
            continue
        if _looks_like_context_phrase(cleaned_name):
            queries.append(cleaned_name)

    return tuple(_dedupe_strings(queries))


def _looks_like_catalog_query_line(line: str) -> bool:
    if not any(character.isalpha() for character in line) or not any(character.isdigit() for character in line):
        return False

    tokens = line.split()
    if len(tokens) > 3:
        return False

    return not (len(tokens) == 2 and tokens[1].isdigit() and len(tokens[1]) == 4)


def _looks_like_slash_identity_query_line(line: str) -> bool:
    parts = [part.strip() for part in re.split(r"\s*/+\s*", line) if part.strip()]
    if len(parts) < 3:
        return False

    first_part_tokens = QUERY_TOKEN_PATTERN.findall(parts[0])
    if len(first_part_tokens) != 1:
        return False
    first_part = first_part_tokens[0]
    if not (
        any(character.isalpha() for character in first_part) and any(character.isdigit() for character in first_part)
    ):
        return False

    return all(_looks_like_context_phrase(part) for part in parts[1:3])


def _looks_like_context_phrase(line: str) -> bool:
    if any(character.isdigit() for character in line):
        return False

    tokens = [token for token in line.split() if token]
    if not (1 <= len(tokens) <= 5):
        return False

    return not all(len(token) <= 2 for token in tokens) and score_search_evidence(line).is_query_worthy


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        key = _normalize_query_key(value)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped_values.append(value)

    return deduped_values


def _normalize_query_key(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _strip_track_query_prefix(value: str) -> str:
    stripped_value = value.strip()
    for pattern in (TRACK_QUERY_DOTTED_PREFIX_PATTERN, TRACK_QUERY_PREFIX_PATTERN):
        match = pattern.match(stripped_value)
        if match is not None:
            return stripped_value[match.end() :].strip(" -./#")
    return stripped_value
