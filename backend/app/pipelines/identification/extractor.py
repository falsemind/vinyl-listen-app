from dataclasses import replace

from app.pipelines.identification.barcode_detector import BarcodeDetector
from app.pipelines.identification.identifier_parser import IdentifierParser
from app.pipelines.identification.models import ExtractedIdentifiers, IdentifierEvidence, OcrTextLine, PreparedImage
from app.pipelines.identification.normalization import catalog_number_keys, catalog_numbers_match, normalize_barcode
from app.pipelines.identification.ocr_backends import OcrCascade, build_default_ocr_cascade
from app.pipelines.identification.ocr_extractor import OcrExtractor
from app.pipelines.identification.ocr_layout_analyzer import analyze_ocr_layout


class IdentifierExtractor:
    def __init__(
        self,
        *,
        barcode_detector: BarcodeDetector | None = None,
        ocr_extractor: OcrExtractor | None = None,
        ocr_backend: OcrCascade | None = None,
        identifier_parser: IdentifierParser | None = None,
    ) -> None:
        self._barcode_detector = barcode_detector or BarcodeDetector()
        self._ocr_backend = ocr_backend or build_default_ocr_cascade(ocr_extractor)
        self._identifier_parser = identifier_parser or IdentifierParser()

    def extract(self, prepared_image: PreparedImage) -> ExtractedIdentifiers:
        detected_barcodes = self._barcode_detector.detect(prepared_image)
        ocr_result = self._ocr_backend.extract(prepared_image)
        identifiers = self._identifier_parser.parse(ocr_result.raw_text, barcodes=detected_barcodes)
        ocr_roles = analyze_ocr_layout(ocr_result.lines)
        return replace(
            identifiers,
            ocr_evidence=ocr_result.lines,
            ocr_roles=ocr_roles,
            identifier_evidence=_merge_identifier_evidence(
                identifiers,
                ocr_lines=ocr_result.lines,
                detected_barcodes=detected_barcodes,
            ),
        )


def _merge_identifier_evidence(
    identifiers: ExtractedIdentifiers,
    *,
    ocr_lines: tuple[OcrTextLine, ...],
    detected_barcodes: tuple[str, ...],
) -> tuple[IdentifierEvidence, ...]:
    enriched_evidence = [
        *_enrich_values(
            kind="barcode",
            values=identifiers.barcodes,
            ocr_lines=ocr_lines,
            detected_barcodes=detected_barcodes,
        ),
        *_enrich_values(kind="catalog_number", values=identifiers.catalog_numbers, ocr_lines=ocr_lines),
        *_enrich_optional_value(kind="artist", value=identifiers.artist, ocr_lines=ocr_lines),
        *_enrich_optional_value(kind="title", value=identifiers.title, ocr_lines=ocr_lines),
        *_enrich_optional_value(kind="label", value=identifiers.label, ocr_lines=ocr_lines),
    ]
    if identifiers.year is not None:
        enriched_evidence.extend(_enrich_optional_value(kind="year", value=str(identifiers.year), ocr_lines=ocr_lines))
    enriched_evidence.extend(
        evidence
        for evidence in identifiers.identifier_evidence
        if not any(
            existing.kind == evidence.kind and existing.value == evidence.value for existing in enriched_evidence
        )
    )
    return tuple(enriched_evidence)


def _enrich_optional_value(
    *,
    kind: str,
    value: str | None,
    ocr_lines: tuple[OcrTextLine, ...],
) -> tuple[IdentifierEvidence, ...]:
    if value is None:
        return ()
    return _enrich_values(kind=kind, values=(value,), ocr_lines=ocr_lines)


def _enrich_values(
    *,
    kind: str,
    values: tuple[str, ...],
    ocr_lines: tuple[OcrTextLine, ...],
    detected_barcodes: tuple[str, ...] = (),
) -> tuple[IdentifierEvidence, ...]:
    evidence: list[IdentifierEvidence] = []
    for value in values:
        line = _find_source_line(kind=kind, value=value, ocr_lines=ocr_lines)
        source = "barcode_detector" if kind == "barcode" and value in detected_barcodes else "parser"
        evidence.append(
            IdentifierEvidence(
                kind=kind,  # type: ignore[arg-type]
                value=value,
                source=line.source if line is not None else source,
                confidence=line.confidence if line is not None else None,
                box=line.box if line is not None else None,
            )
        )
    return tuple(evidence)


def _find_source_line(*, kind: str, value: str, ocr_lines: tuple[OcrTextLine, ...]) -> OcrTextLine | None:
    for line in ocr_lines:
        if _line_matches_identifier(kind=kind, value=value, line_text=line.text):
            return line
    return None


def _line_matches_identifier(*, kind: str, value: str, line_text: str) -> bool:
    if kind == "barcode":
        normalized_value = normalize_barcode(value)
        normalized_line = normalize_barcode(line_text)
        return bool(normalized_value and normalized_line and normalized_value in normalized_line)
    if kind == "catalog_number":
        value_keys = catalog_number_keys(value)
        line_keys = catalog_number_keys(line_text, include_ocr_shadow=True)
        return catalog_numbers_match(value, line_text, allow_right_ocr_shadow=True) or any(
            value_key in line_key for value_key in value_keys for line_key in line_keys
        )

    normalized_value = _normalize_text_key(value)
    normalized_line = _normalize_text_key(line_text)
    return bool(normalized_value and normalized_value in normalized_line)


def _normalize_text_key(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())
