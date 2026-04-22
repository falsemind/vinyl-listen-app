from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BARCODE_VARIANT_NAMES = ("normalized", "grayscale", "threshold")
OCR_VARIANT_NAMES = (
    "grayscale",
    "threshold",
    "threshold_low",
    "inverted_threshold",
    "sharpened",
    "upscaled_grayscale",
    "upscaled_threshold",
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
class ExtractedIdentifiers:
    barcodes: tuple[str, ...] = ()
    catalog_numbers: tuple[str, ...] = ()
    artist: str | None = None
    title: str | None = None
    year: int | None = None
    label: str | None = None
    text_fragments: tuple[str, ...] = ()

    def has_signals(self) -> bool:
        return bool(
            self.barcodes
            or self.catalog_numbers
            or self.artist
            or self.title
            or self.year
            or self.label
            or self.text_fragments
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
