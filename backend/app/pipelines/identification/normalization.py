import re

CATALOG_OCR_SHADOW_TRANSLATION = str.maketrans(
    {
        "O": "0",
        "Q": "0",
        "D": "0",
        "I": "1",
        "L": "1",
        "S": "5",
        "B": "8",
    }
)
GTIN_CHECKSUM_LENGTHS = {8, 12, 13, 14}
OCR_BARCODE_TRANSLATION = str.maketrans(
    {
        "O": "0",
        "o": "0",
        "Q": "0",
        "q": "0",
        "D": "0",
        "I": "1",
        "i": "1",
        "l": "1",
        "S": "5",
        "s": "5",
        "B": "8",
    }
)
TOKEN_PATTERN = re.compile(r"[A-Z]+|\d+")
CATALOG_SUFFIX_OCR_PATTERN = re.compile(
    r"([A-Z]{2,}?)([ -]?)([OQDILSB0-9]{2,6}?)(LP|EP)?$",
    re.IGNORECASE,
)


def normalize_catalog_number(value: str | None) -> str:
    if value is None:
        return ""
    return "".join(character for character in value.upper() if character.isalnum())


def catalog_number_keys(value: str | None, *, include_ocr_shadow: bool = False) -> frozenset[str]:
    normalized_value = normalize_catalog_number(value)
    if not normalized_value:
        return frozenset()

    keys = {normalized_value}
    split_key = "".join(TOKEN_PATTERN.findall(normalized_value))
    if split_key:
        keys.add(split_key)

    if include_ocr_shadow:
        shadow_value = _catalog_ocr_shadow_value(value)
        if shadow_value:
            keys.add(shadow_value)

    return frozenset(key for key in keys if key)


def catalog_numbers_match(
    left: str | None,
    right: str | None,
    *,
    allow_left_ocr_shadow: bool = False,
    allow_right_ocr_shadow: bool = False,
) -> bool:
    left_keys = catalog_number_keys(left, include_ocr_shadow=allow_left_ocr_shadow)
    right_keys = catalog_number_keys(right, include_ocr_shadow=allow_right_ocr_shadow)
    if left_keys & right_keys:
        return True

    return allow_right_ocr_shadow and _catalog_prefix_drop_matches(left_keys, right_keys)


def _catalog_ocr_shadow_value(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned_value = " ".join(value.strip().split())
    match = CATALOG_SUFFIX_OCR_PATTERN.fullmatch(cleaned_value)
    if match is None:
        return None

    prefix, separator, suffix, release_type = match.groups()
    if not any(character.isdigit() for character in suffix):
        return None

    corrected_suffix = suffix.translate(CATALOG_OCR_SHADOW_TRANSLATION)
    corrected_value = f"{prefix.upper()}{separator}{corrected_suffix}{(release_type or '').upper()}"
    normalized_corrected_value = normalize_catalog_number(corrected_value)
    if normalized_corrected_value == normalize_catalog_number(value):
        return None
    return normalized_corrected_value


def _catalog_prefix_drop_matches(left_keys: frozenset[str], right_keys: frozenset[str]) -> bool:
    for left_key in left_keys:
        left_parts = _split_catalog_prefix_and_suffix(left_key)
        if left_parts is None:
            continue

        left_prefix, left_suffix = left_parts
        for right_key in right_keys:
            right_parts = _split_catalog_prefix_and_suffix(right_key)
            if right_parts is None:
                continue

            right_prefix, right_suffix = right_parts
            missing_prefix_length = len(left_prefix) - len(right_prefix)
            if not (1 <= missing_prefix_length <= 2):
                continue
            if left_suffix == right_suffix and left_prefix.endswith(right_prefix):
                return True

    return False


def _split_catalog_prefix_and_suffix(value: str) -> tuple[str, str] | None:
    match = re.fullmatch(r"([A-Z]{3,})(\d{2,6}(?:LP|EP)?)", value)
    if match is None:
        return None
    return match.group(1), match.group(2)


def normalize_barcode(value: str | None) -> str | None:
    if value is None:
        return None
    digits_only = "".join(character for character in value if character.isdigit())
    return digits_only or None


def normalize_or_repair_ocr_barcode(value: str) -> str | None:
    digit_characters: list[str] = []
    repairable_indexes: list[int] = []
    for character in value:
        translated_character = character.translate(OCR_BARCODE_TRANSLATION)
        if not translated_character.isdigit():
            continue

        digit_index = len(digit_characters)
        digit_characters.append(translated_character)
        if not character.isdigit():
            repairable_indexes.append(digit_index)

    digits_only = "".join(digit_characters)
    if len(digits_only) not in GTIN_CHECKSUM_LENGTHS:
        return None
    if is_valid_gtin(digits_only):
        return digits_only
    if value.isdigit():
        return None

    for index in repairable_indexes:
        repaired = _repair_single_barcode_digit(digits_only, index)
        if repaired is not None:
            return repaired

    return None


def is_valid_gtin(value: str) -> bool:
    if len(value) not in GTIN_CHECKSUM_LENGTHS or not value.isdigit():
        return False

    digits = [int(character) for character in value]
    check_digit = digits.pop()
    total = 0
    for position, digit in enumerate(reversed(digits), start=1):
        total += digit * (3 if position % 2 == 1 else 1)
    return (10 - (total % 10)) % 10 == check_digit


def _repair_single_barcode_digit(value: str, index: int) -> str | None:
    if index >= len(value):
        return None

    candidates: list[str] = []
    for digit in "0123456789":
        if digit == value[index]:
            continue
        candidate = f"{value[:index]}{digit}{value[index + 1:]}"
        if is_valid_gtin(candidate):
            candidates.append(candidate)

    return next(iter(candidates)) if len(candidates) == 1 else None
