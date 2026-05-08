from io import BytesIO

from PIL import Image

from app.pipelines.identification.preprocess import ImageProcessor


def test_image_processor_normalizes_and_resizes_images() -> None:
    image_processor = ImageProcessor(max_image_dimension=1200, geometry_preprocess_enabled=False)

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
        "label_catalog_band",
        "label_catalog_band_threshold",
        "label_catalog_band_threshold_low",
        "label_bottom_band",
        "label_bottom_band_threshold",
        "label_bottom_band_threshold_low",
    ]
    assert all(variant.data for variant in prepared_image.variants)
    assert prepared_image.quality is not None
    assert prepared_image.quality.width == 1200
    assert prepared_image.quality.height == 600
    assert prepared_image.quality.min_dimension == 600


def test_image_processor_rejects_invalid_image_bytes() -> None:
    image_processor = ImageProcessor(geometry_preprocess_enabled=False)

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


def test_image_processor_handles_tiny_valid_images() -> None:
    image_processor = ImageProcessor(geometry_preprocess_enabled=False)

    prepared_image = image_processor.prepare(
        filename="tiny.png",
        content_type="image/png",
        data=_build_test_image(width=1, height=1),
    )

    assert prepared_image.width == 1
    assert prepared_image.height == 1
    assert all(variant.data for variant in prepared_image.variants)


def test_image_processor_writes_named_debug_preprocess_images(tmp_path) -> None:
    image_processor = ImageProcessor(debug_output_dir=tmp_path, geometry_preprocess_enabled=False)

    prepared_image = image_processor.prepare(
        filename="Label Scan.JPG",
        content_type="image/jpeg",
        data=_build_test_image(width=10, height=10),
    )

    output_dir = tmp_path / f"label_scan_{prepared_image.digest[:12]}"
    assert (output_dir / "01_normalized.png").exists()
    assert (output_dir / "02_grayscale_raw.png").exists()
    assert (output_dir / "04_grayscale.png").exists()
    assert (output_dir / "12_upscaled_threshold.png").exists()
    assert (output_dir / "13_label_catalog_band.png").exists()
    assert (output_dir / "15_label_catalog_band_threshold_low.png").exists()
    assert (output_dir / "16_label_bottom_band.png").exists()
    assert (output_dir / "18_label_bottom_band_threshold_low.png").exists()
    assert (output_dir / "variants" / "02_grayscale.png").exists()
    assert (output_dir / "variants" / "14_color_blue_right_mid.png").exists()
    assert (output_dir / "variants" / "15_label_catalog_band.png").exists()
    assert (output_dir / "variants" / "18_label_bottom_band.png").exists()


def test_image_processor_skips_geometry_variants_when_opencv_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr("app.pipelines.identification.preprocess._load_opencv", lambda: None)
    image_processor = ImageProcessor(geometry_preprocess_enabled=True)

    prepared_image = image_processor.prepare(
        filename="cover.png",
        content_type="image/png",
        data=_build_test_image(width=40, height=40),
    )

    variant_names = [variant.name for variant in prepared_image.variants]
    assert variant_names[-3:] == [
        "label_bottom_band",
        "label_bottom_band_threshold",
        "label_bottom_band_threshold_low",
    ]
    assert "deskewed" not in variant_names


def test_image_processor_adds_bounded_geometry_variants_when_enabled(monkeypatch, tmp_path) -> None:
    def build_geometry_variant_images(_image: Image.Image) -> dict[str, Image.Image]:
        return {
            "deskewed": Image.new("L", (24, 24), color=255),
            "perspective_corrected": Image.new("RGB", (24, 24), color="white"),
            "label_crop": Image.new("RGB", (18, 18), color="white"),
        }

    monkeypatch.setattr(
        "app.pipelines.identification.preprocess._build_geometry_variant_images",
        build_geometry_variant_images,
    )
    image_processor = ImageProcessor(
        debug_output_dir=tmp_path,
        geometry_preprocess_enabled=True,
        max_geometry_variants=2,
    )

    prepared_image = image_processor.prepare(
        filename="Label Scan.JPG",
        content_type="image/jpeg",
        data=_build_test_image(width=40, height=40),
    )

    variant_names = [variant.name for variant in prepared_image.variants]
    selected_geometry_variants = {
        "deskewed",
        "perspective_corrected",
        "label_crop",
    }.intersection(variant_names)
    assert len(selected_geometry_variants) == 2
    output_dir = tmp_path / f"label_scan_{prepared_image.digest[:12]}"
    assert len(list(output_dir.glob("*_geometry_*.png"))) == 2


def _build_test_image(*, width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
