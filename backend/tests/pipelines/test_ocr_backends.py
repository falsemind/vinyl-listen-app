from io import BytesIO

import pytest
from PIL import Image

from app.pipelines.identification import (
    ImageVariant,
    OcrBackendUnavailableError,
    OcrCascade,
    OcrResult,
    OcrTextLine,
    PaddleOcrVlBackend,
    PreparedImage,
)
from app.pipelines.identification.ocr_backends import build_default_ocr_cascade


class StubOcrBackend:
    def __init__(self, result: OcrResult) -> None:
        self.result = result
        self.calls = 0

    def extract(self, _prepared_image: PreparedImage) -> OcrResult:
        self.calls += 1
        return self.result


class FailingOcrBackend:
    def __init__(self) -> None:
        self.calls = 0

    def extract(self, _prepared_image: PreparedImage) -> OcrResult:
        self.calls += 1
        raise OcrBackendUnavailableError("primary unavailable")


class StubOcrExtractor:
    def extract(self, _prepared_image: PreparedImage) -> str:
        return "Cat No: TOVRI 001"


def test_paddleocr_backend_is_placeholder_until_phase_2() -> None:
    backend = PaddleOcrVlBackend()

    with pytest.raises(OcrBackendUnavailableError):
        backend.extract(_build_prepared_image(width=1200, height=800))


def test_ocr_cascade_returns_primary_result_without_evidence_based_fallback() -> None:
    noisy_lines = tuple(
        OcrTextLine(text=f"NOISE {index} CAT001", confidence=None, source="tesseract") for index in range(41)
    )
    primary = StubOcrBackend(
        OcrResult(
            source="tesseract",
            raw_text="\n".join(line.text for line in noisy_lines),
            lines=noisy_lines,
        )
    )
    fallback = StubOcrBackend(
        OcrResult(
            source="paddleocr_vl",
            raw_text="REAL LABEL CAT002",
            lines=(OcrTextLine(text="REAL LABEL CAT002", confidence=0.9, source="paddleocr_vl"),),
        )
    )
    cascade = OcrCascade(primary_backend=primary, fallback_backend=fallback)

    result = cascade.extract(_build_prepared_image(width=1200, height=800))

    assert result.source == "tesseract"
    assert fallback.calls == 0


def test_ocr_cascade_runs_fallback_when_primary_backend_is_unavailable() -> None:
    primary = FailingOcrBackend()
    fallback = StubOcrBackend(
        OcrResult(
            source="tesseract",
            raw_text="Cat No: TOVRI 001",
            lines=(OcrTextLine(text="Cat No: TOVRI 001", confidence=None, source="tesseract"),),
        )
    )
    cascade = OcrCascade(primary_backend=primary, fallback_backend=fallback)

    result = cascade.extract(_build_prepared_image(width=1200, height=800))

    assert result.source == "tesseract"
    assert primary.calls == 1
    assert fallback.calls == 1


def test_ocr_cascade_reraises_primary_error_without_fallback() -> None:
    cascade = OcrCascade(primary_backend=FailingOcrBackend())

    with pytest.raises(OcrBackendUnavailableError):
        cascade.extract(_build_prepared_image(width=1200, height=800))


def test_build_default_ocr_cascade_routes_paddleocr_to_tesseract_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "identify_ocr_backend", "paddleocr_vl")
    monkeypatch.setattr(settings, "identify_ocr_tesseract_fallback_enabled", True)
    cascade = build_default_ocr_cascade(StubOcrExtractor())

    result = cascade.extract(_build_prepared_image(width=1200, height=800))

    assert result.source == "tesseract"
    assert result.raw_text == "Cat No: TOVRI 001"


def _build_prepared_image(*, width: int, height: int) -> PreparedImage:
    return PreparedImage(
        filename="label.jpg",
        content_type="image/jpeg",
        data=b"image-data",
        size_bytes=10,
        digest="digest",
        width=width,
        height=height,
        variants=(ImageVariant(name="grayscale", data=_build_image_bytes(width=width, height=height)),),
    )


def _build_image_bytes(*, width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height), color=(255, 255, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
