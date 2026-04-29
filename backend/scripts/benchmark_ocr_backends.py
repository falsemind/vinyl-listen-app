import argparse
import os
import statistics
import time
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from app.core.config import settings
from app.pipelines.identification import (
    EasyOcrBackend,
    IdentifierParser,
    ImageProcessor,
    OcrBackend,
    OcrCascade,
    TesseractOcrBackend,
)

BACKEND_CHOICES = ("cascade", "tesseract", "easyocr", "all")


def main() -> None:
    _configure_ssl_certificates()

    parser = argparse.ArgumentParser(description="Compare Tesseract and EasyOCR label extraction latency.")
    parser.add_argument("image_dir", type=Path)
    parser.add_argument("--content-type", default="image/jpeg")
    parser.add_argument(
        "--easyocr-max-side",
        type=int,
        default=settings.identify_easyocr_max_image_dimension,
        help="Resize EasyOCR input variants to this longest edge before OCR.",
    )
    parser.add_argument(
        "--backend",
        choices=BACKEND_CHOICES,
        default="cascade",
        help="OCR backend to run. Use 'all' to compare Tesseract, EasyOCR, and cascade.",
    )
    args = parser.parse_args()

    supported_suffixes = {".jpg", ".jpeg", ".png", ".webp"}
    image_paths = sorted(path for path in args.image_dir.iterdir() if path.suffix.lower() in supported_suffixes)
    processor = ImageProcessor()
    tesseract = TesseractOcrBackend()
    easyocr = EasyOcrBackend(
        gpu=settings.identify_easyocr_gpu,
        min_confidence=settings.identify_easyocr_min_confidence,
        max_image_dimension=args.easyocr_max_side,
    )
    cascade = OcrCascade(primary_backend=tesseract, fallback_backend=easyocr)
    backends = _select_backends(
        args.backend,
        tesseract=tesseract,
        easyocr=easyocr,
        cascade=cascade,
    )

    timings: dict[str, list[float]] = defaultdict(list)
    identifier_parser = IdentifierParser()
    for image_path in image_paths:
        image_bytes = image_path.read_bytes()
        prepared = processor.prepare(filename=image_path.name, content_type=args.content_type, data=image_bytes)
        for backend_name, backend in backends:
            start = time.perf_counter()
            result = backend.extract(prepared)
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
    easyocr: OcrBackend,
    cascade: OcrBackend,
) -> Iterable[tuple[str, OcrBackend]]:
    if selected_backend == "all":
        return (
            ("tesseract", tesseract),
            ("easyocr", easyocr),
            ("cascade", cascade),
        )

    backend_map = {
        "cascade": cascade,
        "tesseract": tesseract,
        "easyocr": easyocr,
    }
    return ((selected_backend, backend_map[selected_backend]),)


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
