from dataclasses import dataclass
from typing import Literal

BARCODE_VARIANT_NAMES = ("normalized", "grayscale", "threshold")
OCR_VARIANT_NAMES = (
    "grayscale",
    "adaptive_threshold",
    "adaptive_threshold_inverted",
    "threshold",
    "threshold_low",
    "inverted_threshold",
    "sharpened",
    "upscaled_grayscale",
    "upscaled_threshold",
    "color_red_center_band",
    "color_blue_center_band",
    "color_red_right_mid",
    "color_blue_right_mid",
)


@dataclass(frozen=True)
class ImageVariant:
    name: str
    data: bytes


@dataclass(frozen=True)
class PreparedImage:
    filename: str
    content_type: str
    data: bytes
    size_bytes: int
    digest: str
    width: int
    height: int
    variants: tuple[ImageVariant, ...]

    def barcode_variants(self) -> tuple[ImageVariant, ...]:
        return tuple(variant for variant in self.variants if variant.name in BARCODE_VARIANT_NAMES)

    def ocr_variants(self) -> tuple[ImageVariant, ...]:
        return tuple(variant for variant in self.variants if variant.name in OCR_VARIANT_NAMES)


@dataclass(frozen=True)
class OcrTextLine:
    text: str
    confidence: float | None
    source: str
    box: tuple[tuple[float, float], ...] | None = None


@dataclass(frozen=True)
class OcrResult:
    source: str
    raw_text: str
    lines: tuple[OcrTextLine, ...] = ()

    def has_text(self) -> bool:
        return bool(self.raw_text.strip() or self.lines)


@dataclass(frozen=True)
class OcrRoleEvidence:
    role: Literal["release_title", "label", "track_text", "catalog_number"]
    text: str
    confidence: float | None
    source: str


@dataclass(frozen=True)
class IdentifierEvidence:
    kind: Literal["barcode", "catalog_number", "artist", "title", "year", "label", "text_fragment"]
    value: str
    source: str
    confidence: float | None = None
    role: str | None = None
    box: tuple[tuple[float, float], ...] | None = None


@dataclass(frozen=True)
class ExtractedIdentifiers:
    barcodes: tuple[str, ...] = ()
    catalog_numbers: tuple[str, ...] = ()
    artist: str | None = None
    title: str | None = None
    year: int | None = None
    label: str | None = None
    text_fragments: tuple[str, ...] = ()
    raw_text: str = ""
    ocr_evidence: tuple[OcrTextLine, ...] = ()
    ocr_roles: tuple[OcrRoleEvidence, ...] = ()
    identifier_evidence: tuple[IdentifierEvidence, ...] = ()

    def has_signals(self) -> bool:
        return bool(
            self.barcodes
            or self.catalog_numbers
            or self.artist
            or self.title
            or self.year
            or self.label
            or self.text_fragments
            or self.raw_text
        )


@dataclass(frozen=True)
class IdentifyCandidate:
    discogs_release_id: int
    release_id: str | None
    artist: str
    title: str
    year: int | None
    label: str | None
    catalog_number: str | None
    barcode: str | None
    cover_image_url: str | None
    match_source: Literal["local", "discogs"]
    matched_on: tuple[str, ...] = ()
    confidence: float = 0.0
    score_trace: tuple[str, ...] = ()
