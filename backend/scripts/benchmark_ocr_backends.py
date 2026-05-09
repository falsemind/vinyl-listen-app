import argparse
import json
import os
import statistics
import time
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.pipelines.identification import (
    ExtractedIdentifiers,
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
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    image_path: Path
    content_type: str
    expected: dict[str, Any]


def main() -> None:
    _configure_ssl_certificates()

    parser = argparse.ArgumentParser(description="Compare OCR backend latency and extracted identifier evidence.")
    parser.add_argument("image_dir", type=Path, nargs="?")
    parser.add_argument("--content-type", default="image/jpeg")
    parser.add_argument(
        "--case-manifest",
        type=Path,
        help="JSON manifest with image paths and expected artist/title/catalog/barcode/query evidence.",
    )
    parser.add_argument("--json-report", type=Path, help="Write a machine-readable benchmark report.")
    parser.add_argument(
        "--backend",
        choices=BACKEND_CHOICES,
        default=settings.identify_ocr_backend,
        help="OCR backend to run. Use 'all' to compare MLX/VLM, PaddleOCR-VL, Tesseract, and auto routing.",
    )
    args = parser.parse_args()

    cases = _load_cases(
        image_dir=args.image_dir,
        case_manifest=args.case_manifest,
        default_content_type=args.content_type,
    )
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
    report_rows: list[dict[str, Any]] = []
    identifier_parser = IdentifierParser()
    for case in cases:
        image_path = case.image_path
        image_bytes = image_path.read_bytes()
        prepared = processor.prepare(filename=image_path.name, content_type=case.content_type, data=image_bytes)
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
            checks = _evaluate_case(identifiers=identifiers, raw_text=result.raw_text, expected=case.expected)
            check_status = "unchecked"
            if case.expected:
                check_status = "pass" if checks["passed"] else "fail"
            report_rows.append(
                {
                    "case": case.name,
                    "image": str(case.image_path),
                    "backend": backend_name,
                    "source": result.source,
                    "elapsed_seconds": elapsed,
                    "line_count": len(result.lines),
                    "identifiers": _format_identifiers(identifiers),
                    "checks": checks,
                }
            )
            print(
                f"{image_path.name}\t{backend_name}\t{result.source}\t{elapsed:.3f}s\t"
                f"{len(result.lines)} lines\tbarcodes={','.join(identifiers.barcodes) or '-'}\t"
                f"catalogs={','.join(identifiers.catalog_numbers) or '-'}\t"
                f"artist={identifiers.artist or '-'}\ttitle={identifiers.title or '-'}\tchecks={check_status}"
            )

    for backend_name, backend_timings in timings.items():
        print(
            f"{backend_name}\tcount={len(backend_timings)} "
            f"median={statistics.median(backend_timings):.3f}s max={max(backend_timings):.3f}s"
        )

    if args.json_report is not None:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(
            json.dumps({"results": report_rows, "summary": _summarize_timings(timings)}, indent=2),
            encoding="utf-8",
        )


def _load_cases(
    *,
    image_dir: Path | None,
    case_manifest: Path | None,
    default_content_type: str,
) -> tuple[BenchmarkCase, ...]:
    if case_manifest is None:
        if image_dir is None:
            raise SystemExit("image_dir is required when --case-manifest is not provided.")
        return tuple(
            BenchmarkCase(
                name=path.stem,
                image_path=path,
                content_type=default_content_type,
                expected={},
            )
            for path in sorted(image_dir.iterdir())
            if path.suffix.lower() in SUPPORTED_SUFFIXES
        )

    raw_manifest = json.loads(case_manifest.read_text(encoding="utf-8"))
    raw_cases = raw_manifest.get("cases", raw_manifest) if isinstance(raw_manifest, dict) else raw_manifest
    if not isinstance(raw_cases, list):
        raise SystemExit("--case-manifest must contain a JSON list or an object with a cases list.")

    cases: list[BenchmarkCase] = []
    for index, raw_case in enumerate(raw_cases, start=1):
        if not isinstance(raw_case, dict):
            raise SystemExit(f"Benchmark case #{index} must be an object.")
        image_value = raw_case.get("image") or raw_case.get("path")
        if not image_value:
            raise SystemExit(f"Benchmark case #{index} is missing image.")

        image_path = Path(str(image_value))
        if not image_path.is_absolute():
            image_root = image_dir if image_dir is not None else case_manifest.parent
            image_path = image_root / image_path
        if not image_path.exists():
            raise SystemExit(f"Benchmark case image does not exist: {image_path}")

        expected = raw_case.get("expected", {})
        if not isinstance(expected, dict):
            raise SystemExit(f"Benchmark case #{index} expected value must be an object.")

        cases.append(
            BenchmarkCase(
                name=str(raw_case.get("name") or image_path.stem),
                image_path=image_path,
                content_type=str(raw_case.get("content_type") or default_content_type),
                expected=expected,
            )
        )
    return tuple(cases)


def _evaluate_case(
    *,
    identifiers: ExtractedIdentifiers,
    raw_text: str,
    expected: dict[str, Any],
) -> dict[str, Any]:
    checks = [
        *_check_optional_text("artist", identifiers.artist, expected.get("artist")),
        *_check_optional_text("title", identifiers.title, expected.get("title")),
        *_check_optional_text("label", identifiers.label, expected.get("label")),
        *_check_optional_int("year", identifiers.year, expected.get("year")),
        *_check_expected_values("catalog_numbers", identifiers.catalog_numbers, expected.get("catalog_numbers")),
        *_check_expected_values("barcodes", identifiers.barcodes, expected.get("barcodes")),
        *_check_expected_values("query_fragments", (raw_text,), expected.get("query_fragments"), substring=True),
    ]
    return {
        "passed": all(check["passed"] for check in checks) if checks else None,
        "items": checks,
    }


def _check_optional_text(name: str, actual: str | None, expected: Any) -> tuple[dict[str, Any], ...]:
    if expected is None:
        return ()
    return (
        {
            "name": name,
            "expected": str(expected),
            "actual": actual,
            "passed": _normalize_text(actual or "") == _normalize_text(str(expected)),
        },
    )


def _check_optional_int(name: str, actual: int | None, expected: Any) -> tuple[dict[str, Any], ...]:
    if expected is None:
        return ()
    return (
        {
            "name": name,
            "expected": expected,
            "actual": actual,
            "passed": actual == int(expected),
        },
    )


def _check_expected_values(
    name: str,
    actual_values: tuple[str, ...],
    expected_values: Any,
    *,
    substring: bool = False,
) -> tuple[dict[str, Any], ...]:
    if expected_values is None:
        return ()
    expected_items = expected_values if isinstance(expected_values, list) else [expected_values]
    normalized_actual = [_normalize_text(value) for value in actual_values]
    checks: list[dict[str, Any]] = []
    for expected in expected_items:
        normalized_expected = _normalize_text(str(expected))
        if substring:
            passed = any(normalized_expected in actual for actual in normalized_actual)
        else:
            passed = normalized_expected in normalized_actual
        checks.append(
            {
                "name": name,
                "expected": str(expected),
                "actual": list(actual_values),
                "passed": passed,
            }
        )
    return tuple(checks)


def _format_identifiers(identifiers: ExtractedIdentifiers) -> dict[str, Any]:
    return {
        "barcodes": identifiers.barcodes,
        "catalog_numbers": identifiers.catalog_numbers,
        "artist": identifiers.artist,
        "title": identifiers.title,
        "year": identifiers.year,
        "label": identifiers.label,
        "text_fragments": identifiers.text_fragments,
    }


def _summarize_timings(timings: dict[str, list[float]]) -> dict[str, dict[str, float | int]]:
    return {
        backend_name: {
            "count": len(backend_timings),
            "median_seconds": statistics.median(backend_timings),
            "max_seconds": max(backend_timings),
        }
        for backend_name, backend_timings in timings.items()
        if backend_timings
    }


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


def _normalize_text(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


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
