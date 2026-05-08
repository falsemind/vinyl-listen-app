import logging
from hashlib import sha256
from importlib import import_module
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageFilter, ImageOps, UnidentifiedImageError

from app.pipelines.identification.models import ImageQualityMetrics, ImageVariant, PreparedImage

logger = logging.getLogger(__name__)

DEFAULT_MAX_IMAGE_DIMENSION = 1800
DEFAULT_THRESHOLD = 160
LOW_THRESHOLD_OFFSET = 25
UPSCALE_FACTOR = 2
ADAPTIVE_THRESHOLD_RADIUS = 16
ADAPTIVE_THRESHOLD_OFFSET = 12
OCR_CROP_TARGET_DIMENSION = 1200
OCR_CROP_REGIONS = {
    "center_band": (0.12, 0.18, 0.90, 0.78),
    "right_mid": (0.48, 0.28, 0.92, 0.68),
}
LABEL_CATALOG_BAND_REGION = (0.18, 0.50, 0.86, 0.74)
LABEL_BOTTOM_BAND_REGION = (0.18, 0.68, 0.88, 0.90)
OCR_COLOR_CHANNELS = {
    "red": 0,
    "blue": 2,
}
GEOMETRY_VARIANT_NAMES = (
    "deskewed",
    "perspective_corrected",
    "label_crop",
    "otsu_threshold",
    "morph_threshold",
)
DEFAULT_MAX_GEOMETRY_VARIANTS = 5
MIN_DESKEW_ANGLE_DEGREES = 1.0
MAX_DESKEW_ANGLE_DEGREES = 12.0


class ImageProcessor:
    def __init__(
        self,
        *,
        max_image_dimension: int = DEFAULT_MAX_IMAGE_DIMENSION,
        threshold: int = DEFAULT_THRESHOLD,
        debug_output_dir: Path | str | None = None,
        geometry_preprocess_enabled: bool | None = None,
        max_geometry_variants: int | None = None,
    ) -> None:
        self._max_image_dimension = max_image_dimension
        self._threshold = threshold
        self._debug_output_dir = Path(debug_output_dir) if debug_output_dir is not None else None
        self._geometry_preprocess_enabled = geometry_preprocess_enabled
        self._max_geometry_variants = max_geometry_variants

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
        ocr_grayscale_image = ImageOps.autocontrast(denoised_image)
        quality = _compute_quality_metrics(ocr_grayscale_image)
        sharpened_image = ocr_grayscale_image.filter(ImageFilter.UnsharpMask(radius=1, percent=180, threshold=3))
        adaptive_threshold_image = _adaptive_threshold_image(ocr_grayscale_image, light_text=False)
        adaptive_threshold_inverted_image = _adaptive_threshold_image(ocr_grayscale_image, light_text=True)
        threshold_image = _threshold_image(ocr_grayscale_image, threshold=self._threshold)
        threshold_low_image = _threshold_image(
            ocr_grayscale_image,
            threshold=max(1, self._threshold - LOW_THRESHOLD_OFFSET),
        )
        inverted_threshold_image = ImageOps.invert(threshold_image)
        upscaled_grayscale_image = _upscale_image(ocr_grayscale_image, factor=UPSCALE_FACTOR)
        upscaled_threshold_image = _threshold_image(upscaled_grayscale_image, threshold=self._threshold)
        color_channel_variants = _build_color_channel_variants(resized_image)
        label_catalog_band_variants = _build_label_catalog_band_variants(resized_image, threshold=self._threshold)
        geometry_variant_images = self._build_geometry_variant_images(resized_image)
        geometry_variants = tuple(
            ImageVariant(name=name, data=_serialize_png(image)) for name, image in geometry_variant_images
        )
        if self._is_geometry_preprocess_enabled():
            logger.info(
                "OpenCV geometry preprocessing variants=%s",
                ",".join(name for name, _image in geometry_variant_images) or "none",
            )
        digest = sha256(data).hexdigest()

        variants = (
            ImageVariant(name="normalized", data=_serialize_png(resized_image)),
            ImageVariant(name="grayscale", data=_serialize_png(ocr_grayscale_image)),
            ImageVariant(name="adaptive_threshold", data=_serialize_png(adaptive_threshold_image)),
            ImageVariant(name="adaptive_threshold_inverted", data=_serialize_png(adaptive_threshold_inverted_image)),
            ImageVariant(name="threshold", data=_serialize_png(threshold_image)),
            ImageVariant(name="threshold_low", data=_serialize_png(threshold_low_image)),
            ImageVariant(name="inverted_threshold", data=_serialize_png(inverted_threshold_image)),
            ImageVariant(name="sharpened", data=_serialize_png(sharpened_image)),
            ImageVariant(name="upscaled_grayscale", data=_serialize_png(upscaled_grayscale_image)),
            ImageVariant(name="upscaled_threshold", data=_serialize_png(upscaled_threshold_image)),
            *color_channel_variants,
            *label_catalog_band_variants,
            *geometry_variants,
        )
        geometry_intermediate_images = tuple(
            (f"{index:02d}_geometry_{name}", image)
            for index, (name, image) in enumerate(geometry_variant_images, start=13 + len(label_catalog_band_variants))
        )
        _write_debug_preprocess_images(
            output_dir=self._resolve_debug_output_dir(),
            filename=filename,
            digest=digest,
            intermediate_images=(
                ("01_normalized", resized_image),
                ("02_grayscale_raw", grayscale_image),
                ("03_denoised", denoised_image),
                ("04_grayscale", ocr_grayscale_image),
                ("05_adaptive_threshold", adaptive_threshold_image),
                ("06_adaptive_threshold_inverted", adaptive_threshold_inverted_image),
                ("07_threshold", threshold_image),
                ("08_threshold_low", threshold_low_image),
                ("09_inverted_threshold", inverted_threshold_image),
                ("10_sharpened", sharpened_image),
                ("11_upscaled_grayscale", upscaled_grayscale_image),
                ("12_upscaled_threshold", upscaled_threshold_image),
                *_variant_debug_images(start_index=13, variants=label_catalog_band_variants),
                *geometry_intermediate_images,
            ),
            variants=variants,
        )

        return PreparedImage(
            filename=filename,
            content_type=content_type,
            data=data,
            size_bytes=len(data),
            digest=digest,
            width=resized_image.width,
            height=resized_image.height,
            variants=variants,
            quality=quality,
        )

    def _resolve_debug_output_dir(self) -> Path | None:
        if self._debug_output_dir is not None:
            return self._debug_output_dir

        from app.core.config import BACKEND_ROOT, settings

        if not settings.identify_debug_preprocess_images_enabled:
            return None

        output_dir = Path(settings.identify_debug_preprocess_images_dir)
        if not output_dir.is_absolute():
            output_dir = BACKEND_ROOT / output_dir
        return output_dir

    def _build_geometry_variant_images(self, image: Image.Image) -> tuple[tuple[str, Image.Image], ...]:
        if not self._is_geometry_preprocess_enabled():
            return ()

        max_variants = self._resolve_max_geometry_variants()
        if max_variants <= 0:
            return ()

        variant_images = _build_geometry_variant_images(image)
        selected_variants = _select_geometry_variant_images(variant_images, max_variants=max_variants)
        return tuple((name, selected_variants[name]) for name in GEOMETRY_VARIANT_NAMES if name in selected_variants)

    def _is_geometry_preprocess_enabled(self) -> bool:
        if self._geometry_preprocess_enabled is not None:
            return self._geometry_preprocess_enabled

        from app.core.config import settings

        return settings.identify_geometry_preprocess_enabled

    def _resolve_max_geometry_variants(self) -> int:
        if self._max_geometry_variants is not None:
            return self._max_geometry_variants

        from app.core.config import settings

        return settings.identify_geometry_preprocess_max_variants


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


def _build_label_catalog_band_variants(image: Image.Image, *, threshold: int) -> tuple[ImageVariant, ...]:
    catalog_band_variants = _build_label_band_variants(
        image,
        region=LABEL_CATALOG_BAND_REGION,
        base_name="label_catalog_band",
        threshold=threshold,
    )
    bottom_band_variants = _build_label_band_variants(
        image,
        region=LABEL_BOTTOM_BAND_REGION,
        base_name="label_bottom_band",
        threshold=threshold,
    )
    return (*catalog_band_variants, *bottom_band_variants)


def _build_label_band_variants(
    image: Image.Image,
    *,
    region: tuple[float, float, float, float],
    base_name: str,
    threshold: int,
) -> tuple[ImageVariant, ...]:
    crop = _crop_region(image, region)
    grayscale_image = ImageOps.autocontrast(ImageOps.grayscale(crop))
    grayscale_image = grayscale_image.filter(ImageFilter.UnsharpMask(radius=1, percent=250, threshold=1))
    grayscale_image = _upscale_crop_for_ocr(grayscale_image)
    threshold_image = _threshold_image(grayscale_image, threshold=threshold)
    threshold_low_image = _threshold_image(grayscale_image, threshold=max(1, threshold - LOW_THRESHOLD_OFFSET))

    return (
        ImageVariant(name=base_name, data=_serialize_png(grayscale_image)),
        ImageVariant(name=f"{base_name}_threshold", data=_serialize_png(threshold_image)),
        ImageVariant(name=f"{base_name}_threshold_low", data=_serialize_png(threshold_low_image)),
    )


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


def _adaptive_threshold_image(image: Image.Image, *, light_text: bool) -> Image.Image:
    local_mean_image = image.filter(ImageFilter.BoxBlur(radius=ADAPTIVE_THRESHOLD_RADIUS))
    contrast_image = (
        ImageChops.subtract(image, local_mean_image) if light_text else ImageChops.subtract(local_mean_image, image)
    )
    return contrast_image.point(lambda value: 0 if value >= ADAPTIVE_THRESHOLD_OFFSET else 255, mode="L")


def _compute_quality_metrics(image: Image.Image) -> ImageQualityMetrics:
    grayscale_image = ImageOps.grayscale(image)
    histogram = grayscale_image.histogram()
    total_pixels = max(1, grayscale_image.width * grayscale_image.height)
    mean_luminance = sum(value * count for value, count in enumerate(histogram)) / total_pixels
    variance = sum(((value - mean_luminance) ** 2) * count for value, count in enumerate(histogram)) / total_pixels
    edge_image = grayscale_image.filter(ImageFilter.FIND_EDGES)
    edge_histogram = edge_image.histogram()
    edge_mean = sum(value * count for value, count in enumerate(edge_histogram)) / total_pixels
    edge_variance = sum(((value - edge_mean) ** 2) * count for value, count in enumerate(edge_histogram)) / total_pixels

    return ImageQualityMetrics(
        width=grayscale_image.width,
        height=grayscale_image.height,
        min_dimension=min(grayscale_image.width, grayscale_image.height),
        blur_score=round(edge_variance, 4),
        mean_luminance=round(mean_luminance, 4),
        dark_pixel_ratio=round(sum(histogram[:25]) / total_pixels, 4),
        bright_pixel_ratio=round(sum(histogram[231:]) / total_pixels, 4),
        glare_ratio=round(sum(histogram[246:]) / total_pixels, 4),
        contrast=round(variance**0.5, 4),
    )


def _build_geometry_variant_images(image: Image.Image) -> dict[str, Image.Image]:
    opencv = _load_opencv()
    if opencv is None:
        logger.info("OpenCV geometry preprocessing skipped because cv2/numpy are unavailable.")
        return {}

    cv2, np = opencv
    rgb_array = np.array(image.convert("RGB"))
    gray_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2GRAY)
    variants: dict[str, Image.Image] = {}

    deskewed_array = _deskew_image_array(gray_array, cv2=cv2, np=np)
    if deskewed_array is not None:
        variants["deskewed"] = _cv_array_to_image(deskewed_array)

    perspective_array = _warp_largest_quadrilateral(rgb_array, cv2=cv2, np=np)
    if perspective_array is not None:
        variants["perspective_corrected"] = _cv_array_to_image(perspective_array)

    label_crop_array = _crop_record_label(rgb_array, cv2=cv2, np=np)
    if label_crop_array is not None:
        variants["label_crop"] = _cv_array_to_image(label_crop_array)

    _threshold_value, otsu_array = cv2.threshold(gray_array, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants["otsu_threshold"] = _cv_array_to_image(otsu_array)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    morph_array = cv2.morphologyEx(otsu_array, cv2.MORPH_CLOSE, kernel)
    variants["morph_threshold"] = _cv_array_to_image(morph_array)

    return variants


def _load_opencv() -> tuple[Any, Any] | None:
    try:
        return import_module("cv2"), import_module("numpy")
    except ImportError:
        return None


def _select_geometry_variant_images(
    variant_images: dict[str, Image.Image],
    *,
    max_variants: int,
) -> dict[str, Image.Image]:
    if len(variant_images) <= max_variants:
        return variant_images

    scored_names = sorted(
        variant_images,
        key=lambda name: _ocr_readability_score(variant_images[name]),
        reverse=True,
    )
    return {name: variant_images[name] for name in scored_names[:max_variants]}


def _ocr_readability_score(image: Image.Image) -> float:
    metrics = _compute_quality_metrics(ImageOps.grayscale(image))
    dark_balance = 1.0 - min(1.0, abs(metrics.dark_pixel_ratio - 0.18) / 0.18)
    return metrics.contrast + (metrics.blur_score * 0.02) + (dark_balance * 20.0)


def _deskew_image_array(gray_array: Any, *, cv2: Any, np: Any) -> Any | None:
    inverted_array = cv2.bitwise_not(gray_array)
    _threshold_value, threshold_array = cv2.threshold(
        inverted_array,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )
    coordinates = np.column_stack(np.where(threshold_array > 0))
    if len(coordinates) < 20:
        return None

    angle = cv2.minAreaRect(coordinates)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    if abs(angle) < MIN_DESKEW_ANGLE_DEGREES or abs(angle) > MAX_DESKEW_ANGLE_DEGREES:
        return None

    height, width = gray_array.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), angle, 1.0)
    return cv2.warpAffine(gray_array, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def _warp_largest_quadrilateral(rgb_array: Any, *, cv2: Any, np: Any) -> Any | None:
    gray_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2GRAY)
    blurred_array = cv2.GaussianBlur(gray_array, (5, 5), 0)
    edged_array = cv2.Canny(blurred_array, 50, 150)
    contours, _hierarchy = cv2.findContours(edged_array, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = rgb_array.shape[0] * rgb_array.shape[1]

    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        perimeter = cv2.arcLength(contour, True)
        approximation = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approximation) != 4 or cv2.contourArea(approximation) < image_area * 0.2:
            continue

        points = _order_quadrilateral_points(approximation.reshape(4, 2), np=np)
        return _four_point_warp(rgb_array, points, cv2=cv2, np=np)

    return None


def _crop_record_label(rgb_array: Any, *, cv2: Any, np: Any) -> Any | None:
    gray_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2GRAY)
    blurred_array = cv2.medianBlur(gray_array, 5)
    min_radius = max(8, min(gray_array.shape[:2]) // 8)
    max_radius = max(min_radius + 1, min(gray_array.shape[:2]) // 2)
    circles = cv2.HoughCircles(
        blurred_array,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(20, min(gray_array.shape[:2]) // 3),
        param1=80,
        param2=28,
        minRadius=min_radius,
        maxRadius=max_radius,
    )
    if circles is None:
        return None

    x_center, y_center, radius = np.round(circles[0][0]).astype("int")
    padding = int(radius * 0.15)
    left = max(0, x_center - radius - padding)
    upper = max(0, y_center - radius - padding)
    right = min(rgb_array.shape[1], x_center + radius + padding)
    lower = min(rgb_array.shape[0], y_center + radius + padding)
    if right <= left or lower <= upper:
        return None
    return rgb_array[upper:lower, left:right]


def _order_quadrilateral_points(points: Any, *, np: Any) -> Any:
    ordered = np.zeros((4, 2), dtype="float32")
    point_sums = points.sum(axis=1)
    ordered[0] = points[np.argmin(point_sums)]
    ordered[2] = points[np.argmax(point_sums)]
    point_diffs = np.diff(points, axis=1)
    ordered[1] = points[np.argmin(point_diffs)]
    ordered[3] = points[np.argmax(point_diffs)]
    return ordered


def _four_point_warp(rgb_array: Any, points: Any, *, cv2: Any, np: Any) -> Any:
    top_left, top_right, bottom_right, bottom_left = points
    width_top = np.linalg.norm(top_right - top_left)
    width_bottom = np.linalg.norm(bottom_right - bottom_left)
    height_right = np.linalg.norm(top_right - bottom_right)
    height_left = np.linalg.norm(top_left - bottom_left)
    max_width = max(1, int(max(width_top, width_bottom)))
    max_height = max(1, int(max(height_right, height_left)))
    destination = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(points, destination)
    return cv2.warpPerspective(rgb_array, matrix, (max_width, max_height))


def _cv_array_to_image(array: Any) -> Image.Image:
    return Image.fromarray(array).convert("L" if len(array.shape) == 2 else "RGB")


def _serialize_png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _write_debug_preprocess_images(
    *,
    output_dir: Path | None,
    filename: str,
    digest: str,
    intermediate_images: tuple[tuple[str, Image.Image], ...],
    variants: tuple[ImageVariant, ...],
) -> None:
    if output_dir is None:
        return

    image_dir = output_dir / f"{_safe_filename_stem(filename)}_{digest[:12]}"
    image_dir.mkdir(parents=True, exist_ok=True)

    for step_name, image in intermediate_images:
        image.save(image_dir / f"{step_name}.png", format="PNG")

    variant_dir = image_dir / "variants"
    variant_dir.mkdir(exist_ok=True)
    for index, variant in enumerate(variants, start=1):
        (variant_dir / f"{index:02d}_{_safe_filename_stem(variant.name)}.png").write_bytes(variant.data)

    logger.info("Wrote OCR preprocess debug images dir=%s variants=%d", image_dir, len(variants))


def _variant_debug_images(
    *,
    start_index: int,
    variants: tuple[ImageVariant, ...],
) -> tuple[tuple[str, Image.Image], ...]:
    images: list[tuple[str, Image.Image]] = []
    for index, variant in enumerate(variants, start=start_index):
        with Image.open(BytesIO(variant.data)) as image:
            images.append((f"{index:02d}_{variant.name}", image.copy()))
    return tuple(images)


def _safe_filename_stem(value: str) -> str:
    stem = Path(value).stem.strip().lower()
    safe_stem = "".join(character if character.isalnum() else "_" for character in stem)
    return "_".join(part for part in safe_stem.split("_") if part) or "image"
