from __future__ import annotations

from hashlib import sha256
from io import BytesIO

from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

from app.pipelines.identification.models import ImageVariant, PreparedImage

DEFAULT_MAX_IMAGE_DIMENSION = 1800
DEFAULT_THRESHOLD = 160


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
        threshold_image = enhanced_image.point(
            lambda value: 255 if value >= self._threshold else 0,
            mode="L",
        )

        variants = (
            ImageVariant(name="normalized", data=_serialize_png(resized_image)),
            ImageVariant(name="grayscale", data=_serialize_png(enhanced_image)),
            ImageVariant(name="threshold", data=_serialize_png(threshold_image)),
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


def _serialize_png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
