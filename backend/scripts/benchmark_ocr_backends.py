import argparse
import os
import statistics
import time
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from app.core.config import settings
from app.pipelines.identification import (
    IdentifierParser,
    ImageProcessor,
    MlxVlmOcrBackend,
    OcrBackend,
    OcrBackendError,
    OcrCascade,
    PaddleOcrVlBackend,
    TesseractOcrBackend,
)

BACKEND_CHOICES = ("auto", "mlx_vlm", "tesseract", "paddleocr_vl", "all")


def main() -> None:
    _configure_ssl_certificates()

    parser = argparse.ArgumentParser(description="Compare OCR backend latency and extracted identifier evidence.")
    parser.add_argument("image_dir", type=Path)
    parser.add_argument("--content-type", default="image/jpeg")
    parser.add_argument(
        "--backend",
        choices=BACKEND_CHOICES,
        default=settings.identify_ocr_backend,
        help="OCR backend to run. Use 'all' to compare MLX/VLM, PaddleOCR-VL, Tesseract, and auto routing.",
    )
    args = parser.parse_args()

    supported_suffixes = {".jpg", ".jpeg", ".png", ".webp"}
    image_paths = sorted(path for path in args.image_dir.iterdir() if path.suffix.lower() in supported_suffixes)
    processor = ImageProcessor()
    tesseract = TesseractOcrBackend()
    mlx_vlm = MlxVlmOcrBackend(
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
    )
    paddleocr_vl = PaddleOcrVlBackend(
        device=settings.identify_paddleocr_device,
        vl_rec_backend=settings.identify_paddleocr_vl_rec_backend,
        vl_rec_server_url=settings.identify_paddleocr_vl_rec_server_url,
        vl_rec_api_model_name=settings.identify_paddleocr_vl_rec_api_model_name,
        vl_rec_api_key=settings.identify_paddleocr_vl_rec_api_key,
        vl_rec_max_concurrency=settings.identify_paddleocr_vl_rec_max_concurrency,
        timeout_seconds=settings.identify_paddleocr_timeout_seconds,
        max_image_dimension=settings.identify_paddleocr_max_image_dimension,
    )
    auto = OcrCascade(
        primary_backend=mlx_vlm,
        fallback_backend=tesseract if settings.identify_ocr_tesseract_fallback_enabled else None,
    )
    backends = _select_backends(
        args.backend,
        tesseract=tesseract,
        mlx_vlm=mlx_vlm,
        paddleocr_vl=paddleocr_vl,
        auto=auto,
    )

    timings: dict[str, list[float]] = defaultdict(list)
    identifier_parser = IdentifierParser()
    for image_path in image_paths:
        image_bytes = image_path.read_bytes()
        prepared = processor.prepare(filename=image_path.name, content_type=args.content_type, data=image_bytes)
        for backend_name, backend in backends:
            start = time.perf_counter()
            try:
                result = backend.extract(prepared)
            except (OcrBackendError, TimeoutError) as error:
                elapsed = time.perf_counter() - start
                print(f"{image_path.name}\t{backend_name}\terror\t{elapsed:.3f}s\t{error}")
                continue

            elapsed = time.perf_counter() - start
            timings[backend_name].append(elapsed)
            identifiers = identifier_parser.parse(result.raw_text)
            print(
                f"{image_path.name}\t{backend_name}\t{result.source}\t{elapsed:.3f}s\t"
                f"{len(result.lines)} lines\tbarcodes={','.join(identifiers.barcodes) or '-'}\t"
                f"catalogs={','.join(identifiers.catalog_numbers) or '-'}\t"
                f"artist={identifiers.artist or '-'}\ttitle={identifiers.title or '-'}"
            )

    for backend_name, backend_timings in timings.items():
        print(
            f"{backend_name}\tcount={len(backend_timings)} "
            f"median={statistics.median(backend_timings):.3f}s max={max(backend_timings):.3f}s"
        )


def _select_backends(
    selected_backend: str,
    *,
    tesseract: OcrBackend,
    mlx_vlm: OcrBackend,
    paddleocr_vl: OcrBackend,
    auto: OcrBackend,
) -> Iterable[tuple[str, OcrBackend]]:
    if selected_backend == "all":
        return (
            ("mlx_vlm", mlx_vlm),
            ("paddleocr_vl", paddleocr_vl),
            ("tesseract", tesseract),
            ("auto", auto),
        )

    backend_map = {
        "auto": auto,
        "mlx_vlm": mlx_vlm,
        "tesseract": tesseract,
        "paddleocr_vl": paddleocr_vl,
    }
    return ((selected_backend, backend_map[selected_backend]),)


def _parse_variant_names(value: str) -> tuple[str, ...]:
    return tuple(name.strip() for name in value.split(",") if name.strip())


def _configure_ssl_certificates() -> None:
    if os.environ.get("SSL_CERT_FILE"):
        return

    try:
        import certifi
    except ImportError:
        return

    os.environ["SSL_CERT_FILE"] = certifi.where()


if __name__ == "__main__":
    main()
