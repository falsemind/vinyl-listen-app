from io import BytesIO

from PIL import Image

from app.pipelines.identification import ImageVariant, PreparedImage
from app.pipelines.identification.ocr_extractor import OcrExtractor


class RecordingOcrExtractor(OcrExtractor):
    def __init__(self, responses: dict[tuple[str, str], str]) -> None:
        super().__init__()
        self._responses = responses
        self.calls: list[tuple[str, str]] = []

    def _read_text(self, _image: Image.Image, *, variant_name: str, config: str) -> str:
        self.calls.append((variant_name, config))
        return self._responses.get((variant_name, config), "")


def test_ocr_extractor_stays_on_fast_path_when_initial_output_is_strong() -> None:
    extractor = RecordingOcrExtractor(
        {
            ("grayscale", "--psm 6"): "SCOTCH BONNET\nSCRUB019\n2019",
        }
    )

    extracted_text = extractor.extract(_build_prepared_image())

    assert extracted_text == "SCOTCH BONNET\nSCRUB019\n2019"
    assert all(variant_name in {"grayscale", "threshold"} for variant_name, _config in extractor.calls)


def test_ocr_extractor_runs_escalation_passes_when_fast_path_is_weak() -> None:
    extractor = RecordingOcrExtractor(
        {
            ("grayscale", "--psm 6"): "amo",
            ("upscaled_threshold", "--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-./ "): (
                "SCRUB019"
            ),
        }
    )

    extracted_text = extractor.extract(_build_prepared_image())

    assert "SCRUB019" in extracted_text
    assert any(variant_name == "upscaled_threshold" for variant_name, _config in extractor.calls)


def _build_prepared_image() -> PreparedImage:
    variant_names = (
        "grayscale",
        "threshold",
        "threshold_low",
        "inverted_threshold",
        "sharpened",
        "upscaled_grayscale",
        "upscaled_threshold",
    )
    return PreparedImage(
        filename="label.jpg",
        content_type="image/jpeg",
        data=b"image-data",
        size_bytes=10,
        digest="digest",
        width=1200,
        height=1200,
        variants=tuple(ImageVariant(name=name, data=_build_variant_image_bytes()) for name in variant_names),
    )


def _build_variant_image_bytes() -> bytes:
    image = Image.new("L", (32, 32), color=255)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
