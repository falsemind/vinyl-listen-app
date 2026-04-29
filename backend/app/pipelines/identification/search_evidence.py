import re
from dataclasses import dataclass

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
MIN_QUERY_EVIDENCE_SCORE = 6.0
GOOD_SUFFIX_TERMS = frozenset({"records", "recordings", "music", "sound", "sounds", "productions"})
RELEASE_TERMS = frozenset({"ep", "lp", "album", "single"})
LOW_VALUE_LINES = frozenset({"the", "side", "sides", "side a", "side b", "this side", "other side"})
LOW_VALUE_TOKENS = frozenset({"the", "side", "sides"})


@dataclass(frozen=True)
class SearchEvidenceScore:
    value: str
    score: float

    @property
    def is_query_worthy(self) -> bool:
        return self.score >= MIN_QUERY_EVIDENCE_SCORE


def score_search_evidence(value: str) -> SearchEvidenceScore:
    normalized_value = " ".join(value.strip().split())
    if not normalized_value:
        return SearchEvidenceScore(value=normalized_value, score=0.0)

    tokens = TOKEN_PATTERN.findall(normalized_value)
    if not tokens:
        return SearchEvidenceScore(value=normalized_value, score=0.0)

    lowered_value = normalized_value.lower()
    lowered_tokens = [token.lower() for token in tokens]
    alpha_tokens = [token for token in tokens if any(character.isalpha() for character in token)]
    score = 0.0

    if lowered_value in LOW_VALUE_LINES:
        score -= 8
    if any(token in LOW_VALUE_TOKENS for token in lowered_tokens) and len(tokens) <= 2:
        score -= 4
    if 2 <= len(tokens) <= 5:
        score += 4
    if normalized_value.upper() == normalized_value and len(alpha_tokens) >= 2:
        score += 3
    if any(token in RELEASE_TERMS for token in lowered_tokens):
        score += 4
    if _looks_like_label_value(lowered_value):
        score += 4
    if _average_alpha_token_length(alpha_tokens) >= 4:
        score += 2
    if _looks_like_title_case_phrase(tokens):
        score += 2
    if tokens[0].upper() == "DJ":
        score += 3

    short_alpha_count = sum(len(token) <= 3 for token in alpha_tokens)
    if len(tokens) > 5:
        score -= 4
    if short_alpha_count * 2 >= len(alpha_tokens) and len(alpha_tokens) >= 3:
        score -= 4
    if sum(len(token) == 1 for token in alpha_tokens) > 1:
        score -= 4
    if _looks_like_mixed_case_noise(tokens):
        score -= 3

    return SearchEvidenceScore(value=normalized_value, score=score)


def _looks_like_label_value(lowered_value: str) -> bool:
    return any(lowered_value == suffix or lowered_value.endswith(f" {suffix}") for suffix in GOOD_SUFFIX_TERMS)


def _average_alpha_token_length(tokens: list[str]) -> float:
    if not tokens:
        return 0.0
    return sum(len(token) for token in tokens) / len(tokens)


def _looks_like_title_case_phrase(tokens: list[str]) -> bool:
    title_case_tokens = [token for token in tokens if token[:1].isupper() and token[1:].islower()]
    return len(tokens) >= 2 and len(title_case_tokens) >= len(tokens) - 1


def _looks_like_mixed_case_noise(tokens: list[str]) -> bool:
    if len(tokens) < 3:
        return False

    uppercase_tokens = sum(token.upper() == token for token in tokens)
    lowercase_tokens = sum(token.lower() == token for token in tokens)
    short_tokens = sum(len(token) <= 3 for token in tokens)
    return uppercase_tokens >= 1 and lowercase_tokens >= 1 and short_tokens >= 2
