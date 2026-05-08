from io import BytesIO

from PIL import Image

from app.pipelines.identification import ImageVariant, PreparedImage
from app.pipelines.identification.ocr_extractor import OcrExtractor


class RecordingOcrExtractor(OcrExtractor):
    def __init__(
        self,
        responses: dict[tuple[str, str], str],
        *,
        data_responses: dict[tuple[str, str], dict[str, list]] | None = None,
    ) -> None:
        super().__init__()
        self._responses = responses
        self._data_responses = data_responses or {}
        self.calls: list[tuple[str, str]] = []
        self.data_calls: list[tuple[str, str]] = []

    def _read_text(self, _image: Image.Image, *, variant_name: str, config: str) -> str:
        self.calls.append((variant_name, config))
        return self._responses.get((variant_name, config), "")

    def _read_data(self, _image: Image.Image, *, variant_name: str, config: str) -> dict[str, list]:
        self.data_calls.append((variant_name, config))
        return self._data_responses.get((variant_name, config), _empty_data())


def test_ocr_extractor_stays_on_fast_path_when_initial_output_is_strong() -> None:
    extractor = RecordingOcrExtractor(
        {
            ("grayscale", "--psm 6"): "SCOTCH BONNET\nSCRUB019\n2019",
        }
    )

    extracted_text = extractor.extract(_build_prepared_image())

    assert extracted_text == "SCOTCH BONNET\nSCRUB019\n2019"
    assert all(variant_name in {"grayscale", "sharpened"} for variant_name, _config in extractor.calls)


def test_ocr_extractor_runs_escalation_passes_when_fast_path_is_weak() -> None:
    extractor = RecordingOcrExtractor(
        {
            ("grayscale", "--psm 6"): "amo",
            ("upscaled_threshold", "--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-./# "): (
                "SCRUB019"
            ),
        }
    )

    extracted_text = extractor.extract(_build_prepared_image())

    assert "SCRUB019" in extracted_text
    assert any(variant_name == "upscaled_threshold" for variant_name, _config in extractor.calls)


def test_ocr_extractor_adds_box_grouped_lines_after_weak_fast_path() -> None:
    extractor = RecordingOcrExtractor(
        {
            ("grayscale", "--psm 6"): "&",
        },
        data_responses={
            (
                "color_blue_right_mid",
                "--psm 11",
            ): {
                "text": ["TOVRI", "001", "45"],
                "conf": ["89", "95", "64"],
                "block_num": [1, 1, 2],
                "par_num": [1, 1, 1],
                "line_num": [1, 1, 1],
                "left": [861, 1152, 924],
                "top": [586, 590, 738],
            },
        },
    )

    extracted_text = extractor.extract(_build_prepared_image())

    assert "TOVRI 001" in extracted_text
    assert ("color_blue_right_mid", "--psm 11") in extractor.data_calls


def _build_prepared_image() -> PreparedImage:
    variant_names = (
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


def _empty_data() -> dict[str, list]:
    return {
        "text": [],
        "conf": [],
        "block_num": [],
        "par_num": [],
        "line_num": [],
        "left": [],
        "top": [],
    }
