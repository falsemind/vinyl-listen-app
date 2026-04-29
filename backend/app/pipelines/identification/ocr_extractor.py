import logging
from io import BytesIO

from PIL import Image

from app.pipelines.identification.models import PreparedImage

logger = logging.getLogger(__name__)

try:
    import pytesseract
    from pytesseract import TesseractNotFoundError
except ImportError:
    pytesseract = None

    class TesseractNotFoundError(RuntimeError):
        """Fallback exception used when pytesseract is unavailable."""


DEFAULT_FAST_CONFIGS = ("--psm 6", "--psm 11")
CATALOG_OCR_WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-./# "
DEFAULT_ESCALATION_CONFIGS = {
    "adaptive_threshold": ("--psm 6", "--psm 11"),
    "adaptive_threshold_inverted": ("--psm 6", "--psm 11"),
    "threshold": ("--psm 6", "--psm 11"),
    "threshold_low": ("--psm 6", "--psm 11"),
    "sharpened": ("--psm 7", "--psm 13"),
    "inverted_threshold": ("--psm 7", "--psm 13"),
    "upscaled_grayscale": ("--psm 7", "--psm 8", "--psm 13"),
    "upscaled_threshold": (
        "--psm 7",
        "--psm 8",
        "--psm 13",
        f"--psm 7 -c tessedit_char_whitelist={CATALOG_OCR_WHITELIST}",
        f"--psm 8 -c tessedit_char_whitelist={CATALOG_OCR_WHITELIST}",
    ),
    "color_red_center_band": ("--psm 6", "--psm 11"),
    "color_blue_center_band": ("--psm 6", "--psm 11"),
    "color_red_right_mid": (
        "--psm 11",
        "--psm 7",
        f"--psm 7 -c tessedit_char_whitelist={CATALOG_OCR_WHITELIST}",
    ),
    "color_blue_right_mid": (
        "--psm 11",
        "--psm 7",
        f"--psm 7 -c tessedit_char_whitelist={CATALOG_OCR_WHITELIST}",
    ),
}
FAST_VARIANT_NAMES = ("grayscale", "sharpened")
BOX_OCR_CONFIGS = {
    "grayscale": ("--psm 11",),
    "adaptive_threshold": ("--psm 11",),
    "adaptive_threshold_inverted": ("--psm 11",),
    "threshold": ("--psm 11",),
    "color_red_center_band": ("--psm 11",),
    "color_blue_center_band": ("--psm 11",),
    "color_red_right_mid": ("--psm 11",),
    "color_blue_right_mid": ("--psm 11",),
}
MIN_BOX_CONFIDENCE = 35.0
MAX_BOX_LINES_PER_PASS = 16


class OcrExtractor:
    def __init__(
        self,
        *,
        fast_configs: tuple[str, ...] = DEFAULT_FAST_CONFIGS,
        escalation_configs: dict[str, tuple[str, ...]] | None = None,
        box_ocr_configs: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        self._fast_configs = fast_configs
        self._escalation_configs = escalation_configs or DEFAULT_ESCALATION_CONFIGS
        self._box_ocr_configs = box_ocr_configs or BOX_OCR_CONFIGS

    def extract(self, prepared_image: PreparedImage) -> str:
        if pytesseract is None:
            logger.debug("OCR extraction unavailable because pytesseract is not installed.")
            return ""

        extracted_chunks: list[str] = []
        seen: set[str] = set()
        variants_by_name = {variant.name: variant for variant in prepared_image.ocr_variants()}

        for variant_name in FAST_VARIANT_NAMES:
            variant = variants_by_name.get(variant_name)
            if variant is None:
                continue
            if not self._run_variant_passes(
                variant_name=variant.name,
                image_bytes=variant.data,
                configs=self._fast_configs,
                extracted_chunks=extracted_chunks,
                seen=seen,
            ):
                return ""

        if _should_escalate_ocr(extracted_chunks):
            logger.debug("OCR fast path was weak; running escalation passes.")
            for variant_name, configs in self._escalation_configs.items():
                variant = variants_by_name.get(variant_name)
                if variant is None:
                    continue
                if not self._run_variant_passes(
                    variant_name=variant.name,
                    image_bytes=variant.data,
                    configs=configs,
                    extracted_chunks=extracted_chunks,
                    seen=seen,
                ):
                    return ""

            for variant_name, configs in self._box_ocr_configs.items():
                variant = variants_by_name.get(variant_name)
                if variant is None:
                    continue
                if not self._run_box_variant_passes(
                    variant_name=variant.name,
                    image_bytes=variant.data,
                    configs=configs,
                    extracted_chunks=extracted_chunks,
                    seen=seen,
                ):
                    return ""

        return "\n".join(extracted_chunks)

    def _run_variant_passes(
        self,
        *,
        variant_name: str,
        image_bytes: bytes,
        configs: tuple[str, ...],
        extracted_chunks: list[str],
        seen: set[str],
    ) -> bool:
        with Image.open(BytesIO(image_bytes)) as image:
            for config in configs:
                try:
                    raw_text = self._read_text(image, variant_name=variant_name, config=config)
                except TesseractNotFoundError:
                    logger.info("OCR extraction unavailable because the tesseract binary is not installed.")
                    return False
                except RuntimeError as error:
                    logger.info("OCR extraction failed: %s", error)
                    return False

                cleaned_text = _clean_ocr_text(raw_text)
                if not cleaned_text or cleaned_text in seen:
                    continue

                seen.add(cleaned_text)
                extracted_chunks.append(cleaned_text)

        return True

    def _run_box_variant_passes(
        self,
        *,
        variant_name: str,
        image_bytes: bytes,
        configs: tuple[str, ...],
        extracted_chunks: list[str],
        seen: set[str],
    ) -> bool:
        with Image.open(BytesIO(image_bytes)) as image:
            for config in configs:
                try:
                    raw_data = self._read_data(image, variant_name=variant_name, config=config)
                except TesseractNotFoundError:
                    logger.info("OCR extraction unavailable because the tesseract binary is not installed.")
                    return False
                except RuntimeError as error:
                    logger.info("OCR box extraction failed: %s", error)
                    return False

                cleaned_text = _clean_ocr_text("\n".join(_extract_box_lines(raw_data)))
                if not cleaned_text or cleaned_text in seen:
                    continue

                seen.add(cleaned_text)
                extracted_chunks.append(cleaned_text)

        return True

    def _read_text(self, image: Image.Image, *, variant_name: str, config: str) -> str:
        logger.debug("Running OCR variant=%s config=%s", variant_name, config)
        return pytesseract.image_to_string(image.copy(), config=config)

    def _read_data(self, image: Image.Image, *, variant_name: str, config: str) -> dict[str, list]:
        logger.debug("Running OCR box variant=%s config=%s", variant_name, config)
        return pytesseract.image_to_data(image.copy(), config=config, output_type=pytesseract.Output.DICT)


def _clean_ocr_text(value: str) -> str:
    lines = [line.strip() for line in value.splitlines()]
    non_empty_lines = [line for line in lines if line]
    return "\n".join(non_empty_lines)


def _should_escalate_ocr(extracted_chunks: list[str]) -> bool:
    if not extracted_chunks:
        return True

    extracted_lines = [line for chunk in extracted_chunks for line in chunk.splitlines() if line]
    if len(extracted_lines) >= 3 and any(len(line) >= 10 for line in extracted_lines):
        return False

    combined_text = " ".join(extracted_lines)
    alphanumeric_count = sum(character.isalnum() for character in combined_text)
    return len(extracted_lines) < 2 or alphanumeric_count < 24


def _extract_box_lines(raw_data: dict[str, list]) -> tuple[str, ...]:
    grouped_words: dict[tuple[int, int, int], list[tuple[int, str]]] = {}
    group_positions: dict[tuple[int, int, int], tuple[int, int]] = {}

    for index, raw_text in enumerate(raw_data.get("text", [])):
        text = " ".join(str(raw_text).strip().split())
        if not text:
            continue

        confidence = _parse_confidence(raw_data.get("conf", []), index)
        if confidence < MIN_BOX_CONFIDENCE:
            continue

        key = (
            _read_int(raw_data.get("block_num", []), index),
            _read_int(raw_data.get("par_num", []), index),
            _read_int(raw_data.get("line_num", []), index),
        )
        left = _read_int(raw_data.get("left", []), index)
        top = _read_int(raw_data.get("top", []), index)

        grouped_words.setdefault(key, []).append((left, text))
        group_positions[key] = (top, left)

    lines: list[str] = []
    for key in sorted(grouped_words, key=lambda value: group_positions.get(value, (0, 0))):
        words = [text for _, text in sorted(grouped_words[key], key=lambda word: word[0])]
        line = " ".join(words)
        if _is_useful_box_line(line):
            lines.append(line)
        if len(lines) == MAX_BOX_LINES_PER_PASS:
            break

    return tuple(lines)


def _parse_confidence(values: list, index: int) -> float:
    try:
        return float(values[index])
    except (IndexError, TypeError, ValueError):
        return -1.0


def _read_int(values: list, index: int) -> int:
    try:
        return int(values[index])
    except (IndexError, TypeError, ValueError):
        return 0


def _is_useful_box_line(value: str) -> bool:
    alphanumeric_count = sum(character.isalnum() for character in value)
    return alphanumeric_count >= 3 and (any(character.isdigit() for character in value) or alphanumeric_count >= 5)
