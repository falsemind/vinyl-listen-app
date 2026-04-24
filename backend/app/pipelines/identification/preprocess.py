from __future__ import annotations

from hashlib import sha256
from io import BytesIO

from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

from app.pipelines.identification.models import ImageVariant, PreparedImage

DEFAULT_MAX_IMAGE_DIMENSION = 1800
DEFAULT_THRESHOLD = 160
LOW_THRESHOLD_OFFSET = 25
UPSCALE_FACTOR = 2
OCR_CROP_TARGET_DIMENSION = 1200
OCR_CROP_REGIONS = {
    "center_band": (0.12, 0.18, 0.90, 0.78),
    "right_mid": (0.48, 0.28, 0.92, 0.68),
}
OCR_COLOR_CHANNELS = {
    "red": 0,
    "blue": 2,
}


class ImageProcessor:
    def __init__(
        self,
        *,
        max_image_dimension: int = DEFAULT_MAX_IMAGE_DIMENSION,
        threshold: int = DEFAULT_THRESHOLD,
    ) -> None:
        self._max_image_dimension = max_image_dimension
        self._threshold = threshold

    def prepare(self, *, filename: str, content_type: str, data: bytes) -> PreparedImage:
        if not data:
            raise ValueError("Uploaded image is empty.")

        try:
            with Image.open(BytesIO(data)) as opened_image:
                normalized_image = ImageOps.exif_transpose(opened_image).convert("RGB")
        except UnidentifiedImageError as error:
            raise ValueError("Uploaded file is not a valid image.") from error

        resized_image = _resize_image(normalized_image, max_image_dimension=self._max_image_dimension)
        grayscale_image = ImageOps.grayscale(resized_image)
        denoised_image = grayscale_image.filter(ImageFilter.MedianFilter(size=3))
        enhanced_image = ImageOps.autocontrast(denoised_image)
        sharpened_image = enhanced_image.filter(ImageFilter.UnsharpMask(radius=1, percent=180, threshold=3))
        threshold_image = _threshold_image(enhanced_image, threshold=self._threshold)
        threshold_low_image = _threshold_image(enhanced_image, threshold=max(1, self._threshold - LOW_THRESHOLD_OFFSET))
        inverted_threshold_image = ImageOps.invert(threshold_image)
        upscaled_grayscale_image = _upscale_image(enhanced_image, factor=UPSCALE_FACTOR)
        upscaled_threshold_image = _threshold_image(upscaled_grayscale_image, threshold=self._threshold)
        color_channel_variants = _build_color_channel_variants(resized_image)

        variants = (
            ImageVariant(name="normalized", data=_serialize_png(resized_image)),
            ImageVariant(name="grayscale", data=_serialize_png(enhanced_image)),
            ImageVariant(name="threshold", data=_serialize_png(threshold_image)),
            ImageVariant(name="threshold_low", data=_serialize_png(threshold_low_image)),
            ImageVariant(name="inverted_threshold", data=_serialize_png(inverted_threshold_image)),
            ImageVariant(name="sharpened", data=_serialize_png(sharpened_image)),
            ImageVariant(name="upscaled_grayscale", data=_serialize_png(upscaled_grayscale_image)),
            ImageVariant(name="upscaled_threshold", data=_serialize_png(upscaled_threshold_image)),
            *color_channel_variants,
        )

        return PreparedImage(
            filename=filename,
            content_type=content_type,
            data=data,
            size_bytes=len(data),
            digest=sha256(data).hexdigest(),
            width=resized_image.width,
            height=resized_image.height,
            variants=variants,
        )


def _resize_image(image: Image.Image, *, max_image_dimension: int) -> Image.Image:
    longest_edge = max(image.width, image.height)
    if longest_edge <= max_image_dimension:
        return image.copy()

    scale = max_image_dimension / float(longest_edge)
    resized_dimensions = (
        max(1, int(image.width * scale)),
        max(1, int(image.height * scale)),
    )
    return image.resize(resized_dimensions, Image.Resampling.LANCZOS)


def _upscale_image(image: Image.Image, *, factor: int) -> Image.Image:
    if factor <= 1:
        return image.copy()

    return image.resize(
        (max(1, image.width * factor), max(1, image.height * factor)),
        Image.Resampling.LANCZOS,
    )


def _upscale_crop_for_ocr(image: Image.Image) -> Image.Image:
    longest_edge = max(image.width, image.height)
    if longest_edge >= OCR_CROP_TARGET_DIMENSION:
        return image.copy()

    scale = max(1, round(OCR_CROP_TARGET_DIMENSION / longest_edge))
    return _upscale_image(image, factor=scale)


def _build_color_channel_variants(image: Image.Image) -> tuple[ImageVariant, ...]:
    variants: list[ImageVariant] = []

    for region_name, box_percentages in OCR_CROP_REGIONS.items():
        crop = _crop_region(image, box_percentages)
        channels = crop.split()

        for channel_name, channel_index in OCR_COLOR_CHANNELS.items():
            channel_image = ImageOps.autocontrast(channels[channel_index])
            channel_image = channel_image.filter(ImageFilter.UnsharpMask(radius=1, percent=250, threshold=1))
            channel_image = _upscale_crop_for_ocr(channel_image)
            variants.append(
                ImageVariant(
                    name=f"color_{channel_name}_{region_name}",
                    data=_serialize_png(channel_image),
                )
            )

    return tuple(variants)


def _crop_region(image: Image.Image, box_percentages: tuple[float, float, float, float]) -> Image.Image:
    left, upper, right, lower = box_percentages
    left_px = min(max(0, int(image.width * left)), image.width - 1)
    upper_px = min(max(0, int(image.height * upper)), image.height - 1)
    box = (
        left_px,
        upper_px,
        min(image.width, max(left_px + 1, int(image.width * right))),
        min(image.height, max(upper_px + 1, int(image.height * lower))),
    )
    return image.crop(box)


def _threshold_image(image: Image.Image, *, threshold: int) -> Image.Image:
    return image.point(
        lambda value: 255 if value >= threshold else 0,
        mode="L",
    )


def _serialize_png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
