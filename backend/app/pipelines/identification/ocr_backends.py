import base64
import json
import logging
import re
import sys
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import Any, Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urljoin

from PIL import Image, UnidentifiedImageError

from app.pipelines.identification.models import OcrResult, OcrTextLine, PreparedImage
from app.pipelines.identification.ocr_extractor import OcrExtractor

logger = logging.getLogger(__name__)

DEFAULT_PADDLEOCR_MODEL_NAME = "PaddlePaddle/PaddleOCR-VL-1.5"
DEFAULT_PADDLEOCR_TIMEOUT_SECONDS = 30.0
DEFAULT_PADDLEOCR_MAX_IMAGE_DIMENSION = 1280
DEFAULT_PADDLEOCR_VARIANT_NAMES = ("normalized", "grayscale", "sharpened")
DEFAULT_MLX_VLM_MODEL_NAME = DEFAULT_PADDLEOCR_MODEL_NAME
DEFAULT_MLX_VLM_ENDPOINT_PATH = "/v1/chat/completions"
DEFAULT_MLX_VLM_TIMEOUT_SECONDS = 30.0
DEFAULT_MLX_VLM_MAX_IMAGE_DIMENSION = 2048
DEFAULT_MLX_VLM_MAX_TOKENS = 768
DEFAULT_MLX_VLM_VARIANT_NAMES = ("normalized", "label_catalog_band", "label_bottom_band", "grayscale", "sharpened")
DEFAULT_MLX_VLM_MAX_VARIANTS = 3
MLX_VLM_SOURCE = "mlx_vlm"
PADDLEOCR_SOURCE = "paddleocr_vl"
OCR_VARIANT_BOILERPLATE_PATTERN = re.compile(r"^\s*image\s+variant\s*:?\s+[-_a-z0-9 ]+\.?\s*$", re.IGNORECASE)
_PADDLEOCR_PIPELINE_CACHE_LOCK = Lock()
_PADDLEOCR_PIPELINE_CACHE: dict["_PaddleOcrPipelineCacheKey", Any] = {}
_PADDLEOCR_VL_CLASS: Any | None = None
OcrServiceRequester = Callable[[str, dict[str, Any], dict[str, str], float], Any]


class OcrBackendError(RuntimeError):
    """Base exception for OCR backend failures that may use fallback routing."""


class OcrBackendUnavailableError(OcrBackendError):
    """Raised when a configured OCR backend cannot run in the current environment."""


class OcrBackendTimeoutError(OcrBackendError):
    """Raised when an OCR backend exceeds its configured time budget."""


class OcrBackend(Protocol):
    def extract(self, prepared_image: PreparedImage) -> OcrResult:
        """Extract OCR text from prepared image variants."""


class TesseractOcrBackend:
    def __init__(self, extractor: OcrExtractor | None = None) -> None:
        self._extractor = extractor or OcrExtractor()

    def extract(self, prepared_image: PreparedImage) -> OcrResult:
        started_at = time.perf_counter()
        raw_text = self._extractor.extract(prepared_image)
        elapsed = time.perf_counter() - started_at
        lines = tuple(OcrTextLine(text=line, confidence=None, source="tesseract") for line in _clean_lines(raw_text))
        logger.info("Tesseract OCR extraction complete lines=%s elapsed=%.3fs", len(lines), elapsed)
        return OcrResult(
            source="tesseract",
            raw_text=raw_text,
            lines=lines,
            elapsed_seconds=elapsed,
        )


class MlxVlmOcrBackend:
    def __init__(
        self,
        *,
        service_url: str | None,
        endpoint_path: str = DEFAULT_MLX_VLM_ENDPOINT_PATH,
        model_name: str = DEFAULT_MLX_VLM_MODEL_NAME,
        api_key: str | None = None,
        timeout_seconds: float = DEFAULT_MLX_VLM_TIMEOUT_SECONDS,
        max_image_dimension: int = DEFAULT_MLX_VLM_MAX_IMAGE_DIMENSION,
        max_tokens: int = DEFAULT_MLX_VLM_MAX_TOKENS,
        prompt: str,
        variant_names: tuple[str, ...] = DEFAULT_MLX_VLM_VARIANT_NAMES,
        max_variants: int = DEFAULT_MLX_VLM_MAX_VARIANTS,
        debug_output_dir: Path | str | None = None,
        requester: OcrServiceRequester | None = None,
    ) -> None:
        self._service_url = service_url
        self._endpoint_path = endpoint_path
        self._model_name = model_name
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._max_image_dimension = max_image_dimension
        self._max_tokens = max_tokens
        self._prompt = prompt
        self._variant_names = variant_names
        self._max_variants = max_variants
        self._debug_output_dir = Path(debug_output_dir) if debug_output_dir is not None else None
        self._requester = requester or _post_json

    def extract(self, prepared_image: PreparedImage) -> OcrResult:
        if not self._service_url:
            raise OcrBackendUnavailableError("MLX/VLM OCR backend requires IDENTIFY_MLX_VLM_SERVICE_URL.")

        image_inputs = _select_ocr_service_image_inputs(
            prepared_image,
            variant_names=self._variant_names,
            max_variants=self._max_variants,
            max_image_dimension=self._max_image_dimension,
        )
        url = _build_service_url(self._service_url, self._endpoint_path)
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        logger.info(
            "MLX/VLM OCR extraction starting filename=%s selected_variants=%s model=%s url=%s",
            prepared_image.filename,
            ",".join(image_input.name for image_input in image_inputs),
            self._model_name,
            url,
        )
        started_at = time.perf_counter()
        debug_output_dir = _resolve_ocr_debug_output_dir(self._debug_output_dir)
        variant_responses: list[_MlxVlmVariantResponse] = []
        for image_input in image_inputs:
            payload = _build_mlx_vlm_payload(
                model_name=self._model_name,
                prompt=self._prompt,
                image_bytes=image_input.data,
                max_tokens=self._max_tokens,
                variant_name=image_input.name,
            )
            try:
                raw_output = self._requester(
                    url,
                    payload,
                    headers,
                    self._timeout_seconds,
                )
            except Exception as error:
                _write_mlx_vlm_debug_error_artifacts(
                    prepared_image=prepared_image,
                    image_input=image_input,
                    url=url,
                    payload=payload,
                    error=error,
                    output_dir=debug_output_dir,
                )
                raise
            variant_responses.append(
                _MlxVlmVariantResponse(
                    image_input=image_input,
                    payload=payload,
                    raw_output=raw_output,
                    lines=_normalize_mlx_vlm_output(raw_output, variant_name=image_input.name),
                )
            )
        elapsed = time.perf_counter() - started_at
        lines = _merge_ocr_lines(response.lines for response in variant_responses)
        _write_mlx_vlm_debug_artifacts(
            prepared_image=prepared_image,
            url=url,
            variant_responses=tuple(variant_responses),
            lines=lines,
            output_dir=debug_output_dir,
        )

        logger.info(
            "MLX/VLM OCR extraction complete lines=%s elapsed=%.3fs model=%s",
            len(lines),
            elapsed,
            self._model_name,
        )
        return OcrResult(
            source=MLX_VLM_SOURCE,
            raw_text="\n".join(line.text for line in lines),
            lines=lines,
            selected_variant_names=tuple(image_input.name for image_input in image_inputs),
            model_name=self._model_name,
            elapsed_seconds=elapsed,
        )


class PaddleOcrVlBackend:
    def __init__(
        self,
        *,
        device: str = "cpu",
        vl_rec_backend: str | None = None,
        vl_rec_server_url: str | None = None,
        vl_rec_api_model_name: str = DEFAULT_PADDLEOCR_MODEL_NAME,
        vl_rec_api_key: str | None = None,
        vl_rec_max_concurrency: int | None = None,
        timeout_seconds: float = DEFAULT_PADDLEOCR_TIMEOUT_SECONDS,
        max_image_dimension: int = DEFAULT_PADDLEOCR_MAX_IMAGE_DIMENSION,
        variant_names: tuple[str, ...] = DEFAULT_PADDLEOCR_VARIANT_NAMES,
        debug_output_dir: Path | str | None = None,
        pipeline_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._device = device
        self._vl_rec_backend = vl_rec_backend
        self._vl_rec_server_url = vl_rec_server_url
        self._vl_rec_api_model_name = vl_rec_api_model_name
        self._vl_rec_api_key = vl_rec_api_key
        self._vl_rec_max_concurrency = vl_rec_max_concurrency
        self._timeout_seconds = timeout_seconds
        self._max_image_dimension = max_image_dimension
        self._variant_names = variant_names
        self._debug_output_dir = Path(debug_output_dir) if debug_output_dir is not None else None
        self._pipeline_factory = pipeline_factory
        self._pipeline: Any | None = None

    def extract(self, prepared_image: PreparedImage) -> OcrResult:
        logger.info(
            "PaddleOCR-VL extraction starting filename=%s variants=%s model=%s backend=%s",
            prepared_image.filename,
            len(prepared_image.variants),
            self._vl_rec_api_model_name,
            self._vl_rec_backend or "default",
        )
        pipeline = self._load_pipeline()
        image_bytes = _select_ocr_service_image_bytes(
            prepared_image,
            variant_names=self._variant_names,
            max_image_dimension=self._max_image_dimension,
        )

        started_at = time.perf_counter()
        try:
            raw_output = _run_with_timeout(
                lambda: self._predict(pipeline, image_bytes),
                timeout_seconds=self._timeout_seconds,
            )
        except OcrBackendError:
            logger.exception("PaddleOCR-VL extraction failed before output normalization.")
            raise
        elapsed = time.perf_counter() - started_at
        lines = _normalize_paddleocr_output(raw_output)
        _write_paddleocr_debug_artifacts(
            prepared_image=prepared_image,
            image_bytes=image_bytes,
            raw_output=raw_output,
            lines=lines,
            output_dir=_resolve_ocr_debug_output_dir(self._debug_output_dir),
        )

        logger.info(
            "PaddleOCR-VL extraction complete lines=%s elapsed=%.3fs model=%s backend=%s",
            len(lines),
            elapsed,
            self._vl_rec_api_model_name,
            self._vl_rec_backend or "default",
        )
        return OcrResult(
            source=PADDLEOCR_SOURCE,
            raw_text="\n".join(line.text for line in lines),
            lines=lines,
            selected_variant_names=_select_existing_variant_names(prepared_image, self._variant_names),
            model_name=self._vl_rec_api_model_name,
            elapsed_seconds=elapsed,
        )

    def _load_pipeline(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline

        if self._pipeline_factory is not None:
            try:
                self._pipeline = self._pipeline_factory()
            except ImportError as error:
                raise OcrBackendUnavailableError(_format_paddleocr_import_error(error)) from error
            except Exception as error:
                raise OcrBackendUnavailableError(
                    f"PaddleOCR-VL pipeline initialization failed: {type(error).__name__}: {error}"
                ) from error
            return self._pipeline

        cache_key = _PaddleOcrPipelineCacheKey(
            device=self._device,
            vl_rec_backend=self._vl_rec_backend,
            vl_rec_server_url=self._vl_rec_server_url,
            vl_rec_api_model_name=self._vl_rec_api_model_name,
            vl_rec_api_key=self._vl_rec_api_key,
            vl_rec_max_concurrency=self._vl_rec_max_concurrency,
        )
        with _PADDLEOCR_PIPELINE_CACHE_LOCK:
            cached_pipeline = _PADDLEOCR_PIPELINE_CACHE.get(cache_key)
            if cached_pipeline is not None:
                self._pipeline = cached_pipeline
                return self._pipeline

            self._pipeline = self._build_pipeline()
            _PADDLEOCR_PIPELINE_CACHE[cache_key] = self._pipeline
            return self._pipeline

    def _build_pipeline(self) -> Any:
        kwargs: dict[str, Any] = {
            "device": self._device,
            "vl_rec_api_model_name": self._vl_rec_api_model_name,
        }
        if self._vl_rec_backend:
            kwargs["vl_rec_backend"] = self._vl_rec_backend
        if self._vl_rec_server_url:
            kwargs["vl_rec_server_url"] = self._vl_rec_server_url
        if self._vl_rec_api_key:
            kwargs["vl_rec_api_key"] = self._vl_rec_api_key
        if self._vl_rec_max_concurrency is not None:
            kwargs["vl_rec_max_concurrency"] = self._vl_rec_max_concurrency

        PaddleOCRVL = _load_paddleocr_vl_class()
        try:
            self._pipeline = PaddleOCRVL(**kwargs)
        except Exception as error:
            raise OcrBackendUnavailableError(
                f"PaddleOCR-VL pipeline initialization failed: {type(error).__name__}: {error}"
            ) from error

        return self._pipeline

    def _predict(self, pipeline: Any, image_bytes: bytes) -> Any:
        with NamedTemporaryFile(suffix=".png") as image_file:
            image_file.write(image_bytes)
            image_file.flush()

            predict = getattr(pipeline, "predict", None)
            if callable(predict):
                return predict(input=image_file.name)
            if callable(pipeline):
                return pipeline(image_file.name)

        raise OcrBackendUnavailableError("PaddleOCR-VL pipeline does not expose predict() or __call__().")


class OcrCascade:
    def __init__(
        self,
        *,
        primary_backend: OcrBackend,
        fallback_backend: OcrBackend | None = None,
    ) -> None:
        self._primary_backend = primary_backend
        self._fallback_backend = fallback_backend

    def extract(self, prepared_image: PreparedImage) -> OcrResult:
        try:
            result = self._primary_backend.extract(prepared_image)
        except (OcrBackendError, TimeoutError) as error:
            if self._fallback_backend is None:
                raise

            fallback_reason = f"primary_failed:{type(error).__name__}"
            logger.info("Running OCR fallback reason=%s detail=%s", fallback_reason, error)
            fallback_result = self._fallback_backend.extract(prepared_image)
            _log_ocr_selection(fallback_result, fallback_reason=fallback_reason)
            return fallback_result

        if result.has_text() or self._fallback_backend is None:
            _log_ocr_selection(result, fallback_reason=None)
            return result

        fallback_reason = "primary_empty_text"
        logger.info("Running OCR fallback reason=%s", fallback_reason)
        fallback_result = self._fallback_backend.extract(prepared_image)
        _log_ocr_selection(fallback_result, fallback_reason=fallback_reason)
        return fallback_result


def _log_ocr_selection(result: OcrResult, *, fallback_reason: str | None) -> None:
    logger.info(
        "OCR backend selected source=%s model=%s elapsed=%.3fs fallback_reason=%s selected_variants=%s",
        result.source,
        result.model_name or "-",
        result.elapsed_seconds if result.elapsed_seconds is not None else -1.0,
        fallback_reason or "-",
        ",".join(result.selected_variant_names) or "-",
    )


def build_default_ocr_cascade(ocr_extractor: OcrExtractor | None = None) -> OcrCascade:
    from app.core.config import settings

    backend_name = settings.identify_ocr_backend.strip().lower()
    tesseract_backend = TesseractOcrBackend(ocr_extractor)

    if backend_name == "tesseract":
        return OcrCascade(primary_backend=tesseract_backend)

    fallback_backend: OcrBackend | None = None
    if settings.identify_ocr_tesseract_fallback_enabled:
        fallback_backend = tesseract_backend

    if backend_name in {"auto", "mlx_vlm"}:
        return OcrCascade(
            primary_backend=MlxVlmOcrBackend(
                service_url=settings.identify_mlx_vlm_service_url,
                endpoint_path=settings.identify_mlx_vlm_endpoint_path,
                model_name=settings.identify_mlx_vlm_model_name,
                api_key=settings.identify_mlx_vlm_api_key,
                timeout_seconds=settings.identify_mlx_vlm_timeout_seconds,
                max_image_dimension=settings.identify_mlx_vlm_max_image_dimension,
                max_tokens=settings.identify_mlx_vlm_max_tokens,
                prompt=settings.identify_mlx_vlm_prompt,
                variant_names=_parse_variant_names(settings.identify_mlx_vlm_variant_names),
                max_variants=settings.identify_mlx_vlm_max_variants,
            ),
            fallback_backend=fallback_backend,
        )

    if backend_name == "paddleocr_vl":
        fallback_backend: OcrBackend | None = None
        if settings.identify_ocr_tesseract_fallback_enabled:
            fallback_backend = tesseract_backend

        return OcrCascade(
            primary_backend=PaddleOcrVlBackend(
                device=settings.identify_paddleocr_device,
                vl_rec_backend=settings.identify_paddleocr_vl_rec_backend,
                vl_rec_server_url=settings.identify_paddleocr_vl_rec_server_url,
                vl_rec_api_model_name=settings.identify_paddleocr_vl_rec_api_model_name,
                vl_rec_api_key=settings.identify_paddleocr_vl_rec_api_key,
                vl_rec_max_concurrency=settings.identify_paddleocr_vl_rec_max_concurrency,
                timeout_seconds=settings.identify_paddleocr_timeout_seconds,
                max_image_dimension=settings.identify_paddleocr_max_image_dimension,
            ),
            fallback_backend=fallback_backend,
        )

    raise ValueError(f"Unsupported OCR backend: {settings.identify_ocr_backend}")


@dataclass(frozen=True)
class _PaddleOcrPipelineCacheKey:
    device: str
    vl_rec_backend: str | None
    vl_rec_server_url: str | None
    vl_rec_api_model_name: str
    vl_rec_api_key: str | None
    vl_rec_max_concurrency: int | None


@dataclass(frozen=True)
class _PaddleTextLine:
    text: str
    confidence: float | None = None
    box: tuple[tuple[float, float], ...] | None = None


@dataclass(frozen=True)
class _VlmTextLine:
    text: str
    confidence: float | None = None
    box: tuple[tuple[float, float], ...] | None = None


@dataclass(frozen=True)
class _OcrServiceImageInput:
    name: str
    data: bytes


@dataclass(frozen=True)
class _MlxVlmVariantResponse:
    image_input: _OcrServiceImageInput
    payload: dict[str, Any]
    raw_output: Any
    lines: tuple[OcrTextLine, ...]


def _build_service_url(service_url: str, endpoint_path: str) -> str:
    normalized_service_url = service_url.rstrip("/") + "/"
    normalized_endpoint_path = endpoint_path.lstrip("/")
    if service_url.rstrip("/").endswith(endpoint_path.rstrip("/")):
        return service_url
    return urljoin(normalized_service_url, normalized_endpoint_path)


def _parse_variant_names(value: str | tuple[str, ...] | list[str]) -> tuple[str, ...]:
    if isinstance(value, tuple):
        return tuple(name.strip() for name in value if name.strip())
    if isinstance(value, list):
        return tuple(str(name).strip() for name in value if str(name).strip())
    return tuple(name.strip() for name in value.split(",") if name.strip())


def _build_mlx_vlm_payload(
    *,
    model_name: str,
    prompt: str,
    image_bytes: bytes,
    max_tokens: int,
    variant_name: str | None = None,
) -> dict[str, Any]:
    data_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")
    prompt_text = prompt if variant_name is None else f"{prompt}\n\nImage variant: {variant_name}."
    return {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
    }


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout_seconds: float) -> Any:
    encoded_payload = json.dumps(payload).encode("utf-8")
    request = urllib_request.Request(url, data=encoded_payload, headers=headers, method="POST")
    try:
        with urllib_request.urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except TimeoutError as error:
        raise OcrBackendTimeoutError(f"MLX/VLM OCR service exceeded {timeout_seconds:.1f}s.") from error
    except urllib_error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        if error.code in {408, 504}:
            raise OcrBackendTimeoutError(f"MLX/VLM OCR service timed out: HTTP {error.code} {detail}") from error
        raise OcrBackendError(f"MLX/VLM OCR service failed: HTTP {error.code} {detail}") from error
    except urllib_error.URLError as error:
        raise OcrBackendUnavailableError(f"MLX/VLM OCR service is unavailable: {error.reason}") from error

    try:
        return json.loads(response_body)
    except json.JSONDecodeError:
        return response_body


def _resolve_ocr_debug_output_dir(explicit_output_dir: Path | None) -> Path | None:
    if explicit_output_dir is not None:
        return explicit_output_dir

    from app.core.config import BACKEND_ROOT, settings

    if not settings.identify_debug_preprocess_images_enabled:
        return None

    output_dir = Path(settings.identify_debug_preprocess_images_dir)
    if not output_dir.is_absolute():
        output_dir = BACKEND_ROOT / output_dir
    return output_dir


def _write_mlx_vlm_debug_artifacts(
    *,
    prepared_image: PreparedImage,
    url: str,
    variant_responses: tuple[_MlxVlmVariantResponse, ...],
    lines: tuple[OcrTextLine, ...],
    output_dir: Path | None,
) -> None:
    if output_dir is None:
        return

    debug_dir = _build_ocr_debug_dir(output_dir=output_dir, prepared_image=prepared_image, source=MLX_VLM_SOURCE)
    first_response = variant_responses[0]
    _write_ocr_debug_common_artifacts(debug_dir=debug_dir, image_bytes=first_response.image_input.data, lines=lines)
    _write_json(debug_dir / "request.json", _sanitize_mlx_vlm_payload(first_response.payload) | {"url": url})
    _write_json(debug_dir / "raw_response.json", first_response.raw_output)
    _write_json(debug_dir / "variants.json", _format_variant_debug_summary(variant_responses))

    variants_dir = debug_dir / "variants"
    variants_dir.mkdir(exist_ok=True)
    for index, variant_response in enumerate(variant_responses, start=1):
        prefix = f"{index:02d}_{_safe_filename_stem(variant_response.image_input.name)}"
        (variants_dir / f"{prefix}.png").write_bytes(variant_response.image_input.data)
        _write_json(
            variants_dir / f"{prefix}_request.json",
            _sanitize_mlx_vlm_payload(variant_response.payload) | {"url": url},
        )
        _write_json(variants_dir / f"{prefix}_raw_response.json", variant_response.raw_output)
        _write_json(variants_dir / f"{prefix}_lines.json", [asdict(line) for line in variant_response.lines])
    logger.info("Wrote MLX/VLM OCR debug artifacts dir=%s", debug_dir)


def _write_mlx_vlm_debug_error_artifacts(
    *,
    prepared_image: PreparedImage,
    image_input: _OcrServiceImageInput,
    url: str,
    payload: dict[str, Any],
    error: Exception,
    output_dir: Path | None,
) -> None:
    if output_dir is None:
        return

    debug_dir = _build_ocr_debug_dir(output_dir=output_dir, prepared_image=prepared_image, source=MLX_VLM_SOURCE)
    (debug_dir / "input.png").write_bytes(image_input.data)
    _write_json(debug_dir / "request.json", _sanitize_mlx_vlm_payload(payload) | {"url": url})
    _write_json(
        debug_dir / "error.json",
        {
            "type": type(error).__name__,
            "message": str(error),
            "variant_name": image_input.name,
        },
    )
    logger.info("Wrote failed MLX/VLM OCR debug artifacts dir=%s", debug_dir)


def _write_paddleocr_debug_artifacts(
    *,
    prepared_image: PreparedImage,
    image_bytes: bytes,
    raw_output: Any,
    lines: tuple[OcrTextLine, ...],
    output_dir: Path | None,
) -> None:
    if output_dir is None:
        return

    debug_dir = _build_ocr_debug_dir(output_dir=output_dir, prepared_image=prepared_image, source=PADDLEOCR_SOURCE)
    _write_ocr_debug_common_artifacts(debug_dir=debug_dir, image_bytes=image_bytes, lines=lines)
    _write_json(debug_dir / "raw_output.json", _json_safe(raw_output))
    _write_paddle_native_debug_outputs(raw_output=raw_output, debug_dir=debug_dir)
    logger.info("Wrote PaddleOCR-VL debug artifacts dir=%s", debug_dir)


def _build_ocr_debug_dir(*, output_dir: Path, prepared_image: PreparedImage, source: str) -> Path:
    image_dir_name = f"{_safe_filename_stem(prepared_image.filename)}_{prepared_image.digest[:12]}"
    debug_dir = output_dir / image_dir_name / "ocr" / source
    debug_dir.mkdir(parents=True, exist_ok=True)
    return debug_dir


def _write_ocr_debug_common_artifacts(
    *,
    debug_dir: Path,
    image_bytes: bytes,
    lines: tuple[OcrTextLine, ...],
) -> None:
    (debug_dir / "input.png").write_bytes(image_bytes)
    _write_json(debug_dir / "normalized_lines.json", [asdict(line) for line in lines])
    (debug_dir / "normalized_lines.md").write_text(_format_ocr_lines_markdown(lines), encoding="utf-8")


def _format_variant_debug_summary(variant_responses: tuple[_MlxVlmVariantResponse, ...]) -> list[dict[str, Any]]:
    return [
        {
            "variant_name": variant_response.image_input.name,
            "line_count": len(variant_response.lines),
            "lines": [line.text for line in variant_response.lines],
        }
        for variant_response in variant_responses
    ]


def _sanitize_mlx_vlm_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized_payload = json.loads(json.dumps(payload, default=str))
    for message in sanitized_payload.get("messages", []):
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            image_url = item.get("image_url") if isinstance(item, dict) else None
            if isinstance(image_url, dict) and isinstance(image_url.get("url"), str):
                image_url["url"] = f"<base64 image omitted; length={len(image_url['url'])}>"
    return sanitized_payload


def _write_paddle_native_debug_outputs(*, raw_output: Any, debug_dir: Path) -> None:
    for index, result in enumerate(_iter_debug_results(raw_output), start=1):
        result_dir = debug_dir / f"paddle_result_{index:02d}"
        result_dir.mkdir(exist_ok=True)
        _call_optional_debug_method(result, "print")
        _call_optional_debug_method(result, "save_to_json", save_path=str(result_dir))
        _call_optional_debug_method(result, "save_to_markdown", save_path=str(result_dir))
        _call_optional_debug_method(result, "save_to_img", save_path=str(result_dir / "images"))


def _iter_debug_results(value: Any) -> Iterable[Any]:
    if isinstance(value, str | bytes | dict):
        return
    if not isinstance(value, Iterable):
        yield value
        return
    yield from value


def _call_optional_debug_method(result: Any, method_name: str, **kwargs: Any) -> None:
    method = getattr(result, method_name, None)
    if not callable(method):
        return
    try:
        method(**kwargs)
    except TypeError:
        method()
    except Exception:
        logger.exception("PaddleOCR-VL debug method failed method=%s", method_name)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(_json_safe(value), indent=2, ensure_ascii=False), encoding="utf-8")


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        pass

    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _json_safe(to_dict())
        except Exception:
            logger.exception("Failed to convert OCR debug value with to_dict().")

    return repr(value)


def _format_ocr_lines_markdown(lines: tuple[OcrTextLine, ...]) -> str:
    if not lines:
        return "# Normalized OCR Lines\n\nNo OCR lines returned.\n"

    rows = [
        "# Normalized OCR Lines",
        "",
        "| # | Text | Confidence | Source | Variant |",
        "|---:|---|---:|---|---|",
    ]
    for index, line in enumerate(lines, start=1):
        confidence = "" if line.confidence is None else f"{line.confidence:.4f}"
        variant_name = line.variant_name or ""
        rows.append(
            f"| {index} | {_escape_markdown_table_text(line.text)} | {confidence} | {line.source} | {variant_name} |"
        )
    return "\n".join(rows) + "\n"


def _escape_markdown_table_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def _safe_filename_stem(value: str) -> str:
    stem = Path(value).stem.strip().lower()
    safe_stem = "".join(character if character.isalnum() else "_" for character in stem)
    return "_".join(part for part in safe_stem.split("_") if part) or "image"


def _load_paddleocr_vl_class() -> Any:
    global _PADDLEOCR_VL_CLASS  # noqa: PLW0603
    if _PADDLEOCR_VL_CLASS is not None:
        return _PADDLEOCR_VL_CLASS

    loaded_paddleocr = sys.modules.get("paddleocr")
    loaded_paddleocr_vl = getattr(loaded_paddleocr, "PaddleOCRVL", None)
    if loaded_paddleocr_vl is not None:
        _PADDLEOCR_VL_CLASS = loaded_paddleocr_vl
        return _PADDLEOCR_VL_CLASS

    try:
        from paddleocr import PaddleOCRVL
    except ImportError as error:
        raise OcrBackendUnavailableError(_format_paddleocr_import_error(error)) from error
    except RuntimeError as error:
        loaded_paddleocr = sys.modules.get("paddleocr")
        loaded_paddleocr_vl = getattr(loaded_paddleocr, "PaddleOCRVL", None)
        if loaded_paddleocr_vl is not None:
            _PADDLEOCR_VL_CLASS = loaded_paddleocr_vl
            return _PADDLEOCR_VL_CLASS
        raise OcrBackendUnavailableError(f"PaddleOCR-VL import failed: {type(error).__name__}: {error}") from error

    _PADDLEOCR_VL_CLASS = PaddleOCRVL
    return _PADDLEOCR_VL_CLASS


def _format_paddleocr_import_error(error: ImportError) -> str:
    if getattr(error, "name", None) == "paddleocr":
        return "PaddleOCR-VL backend requires the paddleocr package."
    return f"PaddleOCR-VL import failed: {type(error).__name__}: {error}"


def _run_with_timeout(call: Callable[[], Any], *, timeout_seconds: float) -> Any:
    if timeout_seconds <= 0:
        return call()

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(call)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError as error:
        future.cancel()
        raise OcrBackendTimeoutError(f"PaddleOCR-VL extraction exceeded {timeout_seconds:.1f}s.") from error
    except OcrBackendError:
        raise
    except Exception as error:
        raise OcrBackendError(f"PaddleOCR-VL extraction failed: {error}") from error
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _select_ocr_service_image_bytes(
    prepared_image: PreparedImage,
    *,
    variant_names: tuple[str, ...],
    max_image_dimension: int,
) -> bytes:
    return _select_ocr_service_image_inputs(
        prepared_image,
        variant_names=variant_names,
        max_variants=1,
        max_image_dimension=max_image_dimension,
    )[0].data


def _select_ocr_service_image_inputs(
    prepared_image: PreparedImage,
    *,
    variant_names: tuple[str, ...],
    max_variants: int,
    max_image_dimension: int,
) -> tuple[_OcrServiceImageInput, ...]:
    variants_by_name = {variant.name: variant for variant in prepared_image.variants}
    selected_inputs: list[_OcrServiceImageInput] = []
    seen_names: set[str] = set()
    for variant_name in variant_names:
        variant = variants_by_name.get(variant_name)
        if variant is None or variant.name in seen_names:
            continue
        seen_names.add(variant.name)
        selected_inputs.append(
            _OcrServiceImageInput(
                name=variant.name,
                data=_resize_image_bytes(variant.data, max_image_dimension=max_image_dimension),
            )
        )
        if 0 < max_variants <= len(selected_inputs):
            break

    if not selected_inputs:
        selected_inputs.append(
            _OcrServiceImageInput(
                name="original",
                data=_resize_image_bytes(prepared_image.data, max_image_dimension=max_image_dimension),
            )
        )

    return tuple(selected_inputs)


def _select_existing_variant_names(prepared_image: PreparedImage, variant_names: tuple[str, ...]) -> tuple[str, ...]:
    variants_by_name = {variant.name for variant in prepared_image.variants}
    for variant_name in variant_names:
        if variant_name in variants_by_name:
            return (variant_name,)
    return ("original",)


def _resize_image_bytes(image_bytes: bytes, *, max_image_dimension: int) -> bytes:
    if max_image_dimension <= 0:
        return image_bytes

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            normalized_image = image.convert("RGB")
            longest_edge = max(normalized_image.width, normalized_image.height)
            if longest_edge <= max_image_dimension:
                return _serialize_png(normalized_image)

            scale = max_image_dimension / float(longest_edge)
            resized_dimensions = (
                max(1, int(normalized_image.width * scale)),
                max(1, int(normalized_image.height * scale)),
            )
            resized_image = normalized_image.resize(resized_dimensions, Image.Resampling.LANCZOS)
            return _serialize_png(resized_image)
    except UnidentifiedImageError as error:
        raise OcrBackendError("Selected OCR image variant is not a valid image.") from error


def _serialize_png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _normalize_paddleocr_output(raw_output: Any) -> tuple[OcrTextLine, ...]:
    normalized_lines: list[OcrTextLine] = []
    seen: set[str] = set()
    for candidate in _iter_paddle_text_lines(raw_output):
        key = _normalize_text_key(candidate.text)
        if not key or key in seen or _is_ocr_variant_boilerplate(candidate.text):
            continue
        seen.add(key)
        normalized_lines.append(
            OcrTextLine(
                text=candidate.text,
                confidence=candidate.confidence,
                source=PADDLEOCR_SOURCE,
                box=candidate.box,
            )
        )
    return tuple(normalized_lines)


def _normalize_mlx_vlm_output(raw_output: Any, *, variant_name: str | None = None) -> tuple[OcrTextLine, ...]:
    normalized_lines: list[OcrTextLine] = []
    seen: set[str] = set()
    content = _extract_mlx_vlm_content(raw_output)
    parsed_content = _parse_jsonish_content(content) if isinstance(content, str) else content

    for candidate in _iter_mlx_vlm_text_lines(parsed_content):
        key = _normalize_text_key(candidate.text)
        if not key or key in seen or _is_ocr_variant_boilerplate(candidate.text):
            continue
        seen.add(key)
        normalized_lines.append(
            OcrTextLine(
                text=candidate.text,
                confidence=candidate.confidence,
                source=MLX_VLM_SOURCE,
                box=candidate.box,
                variant_name=variant_name,
            )
        )
    return tuple(normalized_lines)


def _merge_ocr_lines(line_groups: Iterable[tuple[OcrTextLine, ...]]) -> tuple[OcrTextLine, ...]:
    merged_lines: list[OcrTextLine] = []
    seen: set[str] = set()
    for lines in line_groups:
        for line in lines:
            key = _normalize_text_key(line.text)
            if not key or key in seen:
                continue
            seen.add(key)
            merged_lines.append(line)
    return tuple(merged_lines)


def _extract_mlx_vlm_content(value: Any) -> Any:
    if not isinstance(value, dict):
        return value

    choices = value.get("choices")
    if isinstance(choices, list | tuple) and choices:
        first_choice = choices[0]
        if isinstance(first_choice, dict):
            message = first_choice.get("message")
            if isinstance(message, dict) and message.get("content") is not None:
                return message["content"]
            if first_choice.get("text") is not None:
                return first_choice["text"]

    for key in ("output_text", "raw_text", "text", "content", "response", "result"):
        if value.get(key) is not None:
            return value[key]

    return value


def _parse_jsonish_content(value: str) -> Any:
    stripped = value.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()

    for candidate in (stripped, _extract_json_candidate(stripped)):
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return value


def _extract_json_candidate(value: str) -> str | None:
    starts = [index for index in (value.find("{"), value.find("[")) if index >= 0]
    if not starts:
        return None
    start = min(starts)
    end = max(value.rfind("}"), value.rfind("]"))
    if end <= start:
        return None
    return value[start : end + 1]


def _iter_mlx_vlm_text_lines(value: Any) -> Iterable[_VlmTextLine]:
    if isinstance(value, str):
        yield from _lines_from_text(value, line_type=_VlmTextLine)
        return

    if isinstance(value, dict):
        yield from _iter_mlx_vlm_dict_lines(value)
        return

    if isinstance(value, Iterable):
        for item in value:
            yield from _iter_mlx_vlm_text_lines(item)


def _iter_mlx_vlm_dict_lines(value: dict[str, Any]) -> Iterable[_VlmTextLine]:
    for key in ("visible_lines", "lines", "ocr_lines", "text_lines"):
        lines_value = value.get(key)
        if lines_value is not None:
            yield from _iter_mlx_vlm_text_lines(lines_value)

    for key in ("raw_text", "text", "transcription", "content", "markdown", "ocr_text"):
        text_value = value.get(key)
        if isinstance(text_value, str):
            confidence = _coerce_confidence(value.get("confidence") or value.get("score"))
            box = _coerce_box(value.get("box") or value.get("bbox") or value.get("points"))
            yield from _lines_from_text(text_value, confidence=confidence, box=box, line_type=_VlmTextLine)

    yield from _iter_mlx_vlm_field_lines(value.get("fields"))
    yield from _iter_labeled_values(value=value, key="catalog_numbers", label="Catalog Number")
    yield from _iter_labeled_values(value=value, key="best_discogs_queries", label="Discogs Query")

    for key in ("result", "results", "pages", "blocks", "items", "children"):
        nested_value = value.get(key)
        if nested_value is not None:
            yield from _iter_mlx_vlm_text_lines(nested_value)


def _iter_mlx_vlm_field_lines(value: Any) -> Iterable[_VlmTextLine]:
    if not isinstance(value, dict):
        return

    field_labels = {
        "artist": "Artist",
        "title": "Title",
        "release_title": "Title",
        "label": "Label",
        "catalog_number": "Catalog Number",
        "catalog_numbers": "Catalog Number",
        "catno": "Catalog Number",
        "barcode": "Barcode",
        "barcodes": "Barcode",
        "year": "Year",
    }
    for key, label in field_labels.items():
        field_value = value.get(key)
        if field_value is None:
            continue
        if isinstance(field_value, list | tuple):
            for item in field_value:
                text = _normalize_text(str(item))
                if text and text.lower() not in {"none", "null", "unknown"}:
                    yield _VlmTextLine(text=f"{label}: {text}")
            continue
        text = _normalize_text(str(field_value))
        if text and text.lower() not in {"none", "null", "unknown"}:
            yield _VlmTextLine(text=f"{label}: {text}")


def _iter_labeled_values(*, value: dict[str, Any], key: str, label: str) -> Iterable[_VlmTextLine]:
    field_value = value.get(key)
    if field_value is None:
        return
    if isinstance(field_value, list | tuple):
        for item in field_value:
            text = _normalize_text(str(item))
            if text and text.lower() not in {"none", "null", "unknown"}:
                yield _VlmTextLine(text=f"{label}: {text}")
        return
    text = _normalize_text(str(field_value))
    if text and text.lower() not in {"none", "null", "unknown"}:
        yield _VlmTextLine(text=f"{label}: {text}")


def _iter_paddle_text_lines(value: Any) -> Iterable[_PaddleTextLine]:
    normalized_value = _unwrap_paddle_result(value)

    if isinstance(normalized_value, str):
        yield from _lines_from_text(normalized_value)
        return

    if isinstance(normalized_value, dict):
        yield from _iter_paddle_dict_lines(normalized_value)
        return

    if isinstance(normalized_value, Iterable):
        for item in normalized_value:
            yield from _iter_paddle_text_lines(item)


def _unwrap_paddle_result(value: Any) -> Any:
    if isinstance(value, dict | list | tuple | str):
        return value

    for attribute_name in ("json", "res"):
        attribute = getattr(value, attribute_name, None)
        if attribute is not None:
            return attribute() if callable(attribute) else attribute

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()

    return value


def _iter_paddle_dict_lines(value: dict[str, Any]) -> Iterable[_PaddleTextLine]:
    rec_texts = value.get("rec_texts")
    if isinstance(rec_texts, list | tuple):
        scores = value.get("rec_scores")
        boxes = value.get("rec_polys") or value.get("rec_boxes") or value.get("dt_polys")
        for index, text in enumerate(rec_texts):
            normalized_text = _normalize_text(str(text))
            if not normalized_text:
                continue
            yield _PaddleTextLine(
                text=normalized_text,
                confidence=_coerce_indexed_confidence(scores, index),
                box=_coerce_indexed_box(boxes, index),
            )

    for key in ("text", "transcription", "content", "markdown"):
        text_value = value.get(key)
        if isinstance(text_value, str):
            confidence = _coerce_confidence(value.get("confidence") or value.get("score"))
            box = _coerce_box(value.get("box") or value.get("bbox") or value.get("points"))
            yield from _lines_from_text(text_value, confidence=confidence, box=box)

    for key in ("res", "result", "results", "pages", "blocks", "items", "children"):
        nested_value = value.get(key)
        if nested_value is not None:
            yield from _iter_paddle_text_lines(nested_value)


def _lines_from_text(
    value: str,
    *,
    confidence: float | None = None,
    box: tuple[tuple[float, float], ...] | None = None,
    line_type: type[_PaddleTextLine] | type[_VlmTextLine] = _PaddleTextLine,
) -> Iterable[_PaddleTextLine | _VlmTextLine]:
    for line in _clean_lines(value):
        yield line_type(text=line, confidence=confidence, box=box)


def _coerce_indexed_confidence(values: Any, index: int) -> float | None:
    if not isinstance(values, list | tuple):
        return None
    try:
        return _coerce_confidence(values[index])
    except IndexError:
        return None


def _coerce_confidence(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_indexed_box(values: Any, index: int) -> tuple[tuple[float, float], ...] | None:
    if not isinstance(values, list | tuple):
        return None
    try:
        return _coerce_box(values[index])
    except IndexError:
        return None


def _coerce_box(value: Any) -> tuple[tuple[float, float], ...] | None:
    if not isinstance(value, list | tuple):
        return None

    if len(value) == 4 and all(_is_number(coordinate) for coordinate in value):
        left, top, right, bottom = (float(coordinate) for coordinate in value)
        return ((left, top), (right, top), (right, bottom), (left, bottom))

    points: list[tuple[float, float]] = []
    for point in value:
        if not isinstance(point, list | tuple) or len(point) < 2:
            return None
        try:
            points.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError):
            return None
    return tuple(points) or None


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _clean_lines(raw_text: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in raw_text.splitlines() if line.strip())


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def _normalize_text_key(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _is_ocr_variant_boilerplate(value: str) -> bool:
    return OCR_VARIANT_BOILERPLATE_PATTERN.fullmatch(value) is not None
