import re
from dataclasses import dataclass

from app.pipelines.identification.models import OcrRoleEvidence, OcrTextLine

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
LABEL_SUFFIXES = frozenset({"records", "recordings", "music", "sound", "sounds", "productions"})
TITLE_TERMS = frozenset({"ep", "lp", "album", "single", "vol", "volume"})
LOW_VALUE_LINES = frozenset({"side a", "side b", "the", "a", "b"})
MAX_ROLE_VALUES = 3


def analyze_ocr_layout(lines: tuple[OcrTextLine, ...]) -> tuple[OcrRoleEvidence, ...]:
    analyzed_lines = [_AnalyzedLine.from_ocr_line(line, index=index) for index, line in enumerate(lines)]
    analyzed_lines = [line for line in analyzed_lines if line is not None]

    roles: list[OcrRoleEvidence] = []
    roles.extend(_release_title_roles(analyzed_lines))
    roles.extend(_label_roles(analyzed_lines))
    return tuple(_dedupe_roles(roles))


def _release_title_roles(lines: list["_AnalyzedLine"]) -> tuple[OcrRoleEvidence, ...]:
    candidates: list[tuple[float, _AnalyzedLine]] = []

    for line in lines:
        if not _looks_like_release_title(line.text):
            continue

        score = line.height or 0.0
        tokens = _tokens(line.text)
        if any(token.lower() in TITLE_TERMS for token in tokens):
            score += 18
        if line.text.upper() == line.text and len(tokens) >= 2:
            score += 8
        score -= line.index * 0.15
        candidates.append((score, line))

    candidates.sort(key=lambda candidate: candidate[0], reverse=True)
    return tuple(
        OcrRoleEvidence(
            role="release_title",
            text=line.text,
            confidence=line.confidence,
            source=line.source,
        )
        for _, line in candidates[:MAX_ROLE_VALUES]
    )


def _label_roles(lines: list["_AnalyzedLine"]) -> tuple[OcrRoleEvidence, ...]:
    roles: list[OcrRoleEvidence] = []

    for index, line in enumerate(lines):
        lowered_text = line.text.lower()
        if lowered_text in LABEL_SUFFIXES and index > 0:
            previous_text = _strip_leading_noise_token(lines[index - 1].text)
            if previous_text and any(character.isalpha() for character in previous_text):
                roles.append(
                    OcrRoleEvidence(
                        role="label",
                        text=f"{previous_text} {line.text}",
                        confidence=line.confidence,
                        source=line.source,
                    )
                )
                continue

        if _looks_like_label_text(line.text):
            roles.append(OcrRoleEvidence(role="label", text=line.text, confidence=line.confidence, source=line.source))
            continue

    return tuple(roles[:MAX_ROLE_VALUES])


def _looks_like_release_title(value: str) -> bool:
    lowered_value = value.lower()
    if lowered_value in LOW_VALUE_LINES or _looks_like_side_line(value):
        return False
    if _looks_like_label_text(value):
        return False
    if any(character.isdigit() for character in value):
        return False

    tokens = _tokens(value)
    if not (2 <= len(tokens) <= 5):
        return False
    if not any(len(token) >= 3 for token in tokens):
        return False

    if TITLE_TERMS.intersection(token.lower() for token in tokens):
        return True

    return (
        value.upper() == value and max(len(token) for token in tokens) >= 5 and all(len(token) > 1 for token in tokens)
    )


def _looks_like_label_text(value: str) -> bool:
    lowered_value = value.lower()
    return any(lowered_value == suffix or lowered_value.endswith(f" {suffix}") for suffix in LABEL_SUFFIXES)


def _looks_like_side_line(value: str) -> bool:
    lowered_value = value.lower()
    return lowered_value.startswith(("side ", "this side", "other side"))


def _strip_leading_noise_token(value: str) -> str | None:
    tokens = value.split()
    if len(tokens) >= 2 and len(tokens[0]) == 1:
        return " ".join(tokens[1:])
    return value or None


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(match.group(0) for match in TOKEN_PATTERN.finditer(value))


def _dedupe_roles(roles: list[OcrRoleEvidence]) -> tuple[OcrRoleEvidence, ...]:
    deduped_roles: list[OcrRoleEvidence] = []
    seen: set[tuple[str, str]] = set()

    for role in roles:
        key = (role.role, _normalize_key(role.text))
        if key[1] == "" or key in seen:
            continue
        seen.add(key)
        deduped_roles.append(role)

    return tuple(deduped_roles)


def _normalize_key(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


@dataclass(frozen=True)
class _AnalyzedLine:
    index: int
    text: str
    confidence: float | None
    source: str
    height: float | None

    @classmethod
    def from_ocr_line(cls, line: OcrTextLine, *, index: int) -> "_AnalyzedLine | None":
        text = " ".join(line.text.strip(" |\\/.,:;\"'‘’“”`").split())
        if not text:
            return None

        return cls(
            index=index,
            text=text,
            confidence=line.confidence,
            source=line.source,
            height=_box_height(line.box),
        )


def _box_height(box: tuple[tuple[float, float], ...] | None) -> float | None:
    if not box:
        return None
    y_values = [point[1] for point in box]
    return max(y_values) - min(y_values)
