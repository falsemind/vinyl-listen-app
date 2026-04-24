from io import BytesIO

from PIL import Image

from app.pipelines.identification.preprocess import ImageProcessor


def test_image_processor_normalizes_and_resizes_images() -> None:
    image_processor = ImageProcessor(max_image_dimension=1200)

    image_bytes = _build_test_image(width=2400, height=1200)
    prepared_image = image_processor.prepare(
        filename="cover.png",
        content_type="image/png",
        data=image_bytes,
    )

    assert prepared_image.filename == "cover.png"
    assert prepared_image.width == 1200
    assert prepared_image.height == 600
    assert [variant.name for variant in prepared_image.variants] == [
        "normalized",
        "grayscale",
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
    ]
    assert all(variant.data for variant in prepared_image.variants)


def test_image_processor_rejects_invalid_image_bytes() -> None:
    image_processor = ImageProcessor()

    try:
        image_processor.prepare(
            filename="invalid.png",
            content_type="image/png",
            data=b"not-an-image",
        )
    except ValueError as error:
        assert str(error) == "Uploaded file is not a valid image."
    else:
        raise AssertionError("Expected ValueError for invalid image bytes")


def _build_test_image(*, width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
