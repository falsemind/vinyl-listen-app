from io import BytesIO

from PIL import Image

from app.pipelines.identification import EasyOcrBackend, ImageVariant, OcrCascade, OcrResult, OcrTextLine, PreparedImage


class StubOcrBackend:
    def __init__(self, result: OcrResult) -> None:
        self.result = result
        self.calls = 0

    def extract(self, _prepared_image: PreparedImage) -> OcrResult:
        self.calls += 1
        return self.result


class RecordingEasyOcrReader:
    def __init__(self) -> None:
        self.image_sizes: list[tuple[int, int]] = []

    def readtext(self, image_array, *, detail: int, paragraph: bool) -> list:
        del detail, paragraph
        height, width = image_array.shape[:2]
        self.image_sizes.append((width, height))
        return [([[0, 0], [10, 0], [10, 10], [0, 10]], "CAT 001", 0.9)]


def test_easyocr_backend_downscales_large_variants_before_reading() -> None:
    reader = RecordingEasyOcrReader()
    backend = EasyOcrBackend(
        max_image_dimension=320,
        variant_names=("grayscale",),
        reader_factory=lambda: reader,
    )

    result = backend.extract(_build_prepared_image(width=1200, height=800))

    assert result.raw_text == "CAT 001"
    assert reader.image_sizes == [(320, 213)]


def test_ocr_cascade_runs_fallback_when_tesseract_output_is_noisy() -> None:
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
            source="easyocr",
            raw_text="REAL LABEL CAT002",
            lines=(OcrTextLine(text="REAL LABEL CAT002", confidence=0.9, source="easyocr"),),
        )
    )
    cascade = OcrCascade(primary_backend=primary, fallback_backend=fallback)

    result = cascade.extract(_build_prepared_image(width=1200, height=800))

    assert result.source == "tesseract+easyocr"
    assert fallback.calls == 1


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
