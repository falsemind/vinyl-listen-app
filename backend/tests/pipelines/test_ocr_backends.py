import builtins
import json
import sys
import time
import types
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.pipelines.identification import (
    ImageVariant,
    MlxVlmOcrBackend,
    OcrBackendTimeoutError,
    OcrBackendUnavailableError,
    OcrCascade,
    OcrResult,
    OcrTextLine,
    PaddleOcrVlBackend,
    PreparedImage,
    ocr_backends,
)


class StubOcrBackend:
    def __init__(self, result: OcrResult) -> None:
        self.result = result
        self.calls = 0

    def extract(self, _prepared_image: PreparedImage) -> OcrResult:
        self.calls += 1
        return self.result


class FailingOcrBackend:
    def __init__(self) -> None:
        self.calls = 0

    def extract(self, _prepared_image: PreparedImage) -> OcrResult:
        self.calls += 1
        raise OcrBackendUnavailableError("primary unavailable")


class StubOcrExtractor:
    def extract(self, _prepared_image: PreparedImage) -> str:
        return "Cat No: TOVRI 001"


class FakePaddleOcrPipeline:
    def __init__(self, output: object) -> None:
        self.output = output
        self.inputs: list[str] = []

    def predict(self, *, input: str) -> object:
        self.inputs.append(input)
        return self.output


class SlowPaddleOcrPipeline:
    def predict(self, *, input: str) -> object:
        del input
        time.sleep(0.05)
        return {"rec_texts": ["too late"]}


class FakePaddleDebugResult:
    def __init__(self) -> None:
        self.print_called = False
        self.save_paths: list[tuple[str, str]] = []

    def to_dict(self) -> dict[str, object]:
        return {"rec_texts": ["Cat No: DEBUG 001"], "rec_scores": [0.88]}

    def print(self) -> None:
        self.print_called = True

    def save_to_json(self, *, save_path: str) -> None:
        self.save_paths.append(("json", save_path))
        Path(save_path).mkdir(parents=True, exist_ok=True)
        (Path(save_path) / "debug.json").write_text("{}", encoding="utf-8")

    def save_to_markdown(self, *, save_path: str) -> None:
        self.save_paths.append(("markdown", save_path))
        Path(save_path).mkdir(parents=True, exist_ok=True)
        (Path(save_path) / "debug.md").write_text("# debug", encoding="utf-8")

    def save_to_img(self, *, save_path: str) -> None:
        self.save_paths.append(("image", save_path))
        Path(save_path).mkdir(parents=True, exist_ok=True)


def _build_unavailable_paddle_backend(**_kwargs: object) -> FailingOcrBackend:
    return FailingOcrBackend()


def _build_unavailable_mlx_backend(**_kwargs: object) -> FailingOcrBackend:
    return FailingOcrBackend()


def test_mlx_vlm_backend_posts_openai_request_and_normalizes_json_response() -> None:
    calls: list[tuple[str, dict[str, object], dict[str, str], float]] = []

    def requester(url: str, payload: dict[str, object], headers: dict[str, str], timeout: float) -> object:
        calls.append((url, payload, headers, timeout))
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "lines": [{"text": "Cat No: MLX 001", "confidence": 0.94}],
                                "fields": {"artist": "Autechre", "title": "Tri Repetae"},
                            }
                        )
                    }
                }
            ]
        }

    backend = MlxVlmOcrBackend(
        service_url="http://ocr-service:8111",
        model_name="local-vlm",
        api_key="secret",
        prompt="extract text",
        max_image_dimension=320,
        requester=requester,
    )

    result = backend.extract(_build_prepared_image(width=1200, height=800))

    assert result.source == "mlx_vlm"
    assert [line.text for line in result.lines] == ["Cat No: MLX 001", "Artist: Autechre", "Title: Tri Repetae"]
    assert result.lines[0].confidence == 0.94
    assert result.lines[0].variant_name == "grayscale"
    assert result.selected_variant_names == ("grayscale",)
    assert result.model_name == "local-vlm"
    assert calls[0][0] == "http://ocr-service:8111/v1/chat/completions"
    assert calls[0][2]["Authorization"] == "Bearer secret"
    assert calls[0][3] == 30.0
    assert calls[0][1]["model"] == "local-vlm"
    image_url = calls[0][1]["messages"][0]["content"][1]["image_url"]["url"]  # type: ignore[index]
    assert image_url.startswith("data:image/png;base64,")


def test_mlx_vlm_backend_sweeps_bounded_variants_and_merges_structured_identity() -> None:
    calls: list[str] = []

    def requester(_url: str, payload: dict[str, object], _headers: dict[str, str], _timeout: float) -> object:
        prompt_text = payload["messages"][0]["content"][0]["text"]  # type: ignore[index]
        variant_name = str(prompt_text).rsplit("Image variant: ", maxsplit=1)[1].rstrip(".")
        calls.append(variant_name)
        if variant_name == "normalized":
            return {"choices": [{"message": {"content": '{"visible_lines":["HARMONY & KID LIB"]}'}}]}
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "catalog_numbers": ["DAT 095"],
                                "best_discogs_queries": ["HARMONY KID LIB DAT 095"],
                            }
                        )
                    }
                }
            ]
        }

    backend = MlxVlmOcrBackend(
        service_url="http://ocr-service:8111",
        prompt="extract text",
        variant_names=("normalized", "grayscale", "sharpened"),
        max_variants=2,
        requester=requester,
    )

    result = backend.extract(_build_prepared_image(width=1200, height=800, variant_names=("normalized", "grayscale")))

    assert calls == ["normalized", "grayscale"]
    assert result.selected_variant_names == ("normalized", "grayscale")
    assert [line.text for line in result.lines] == [
        "HARMONY & KID LIB",
        "Catalog Number: DAT 095",
        "Discogs Query: HARMONY KID LIB DAT 095",
    ]
    assert result.lines[1].variant_name == "grayscale"


def test_mlx_vlm_backend_writes_debug_artifacts(tmp_path: Path) -> None:
    def requester(_url: str, _payload: dict[str, object], _headers: dict[str, str], _timeout: float) -> object:
        return {"choices": [{"message": {"content": '{"lines":["Cat No: DEBUG 001"]}'}}]}

    backend = MlxVlmOcrBackend(
        service_url="http://ocr-service:8111",
        prompt="extract text",
        debug_output_dir=tmp_path,
        requester=requester,
    )

    result = backend.extract(_build_prepared_image(width=1200, height=800))

    assert result.raw_text == "Cat No: DEBUG 001"
    debug_dir = tmp_path / "label_digest" / "ocr" / "mlx_vlm"
    assert (debug_dir / "input.png").exists()
    assert (debug_dir / "variants.json").exists()
    assert (debug_dir / "variants" / "01_grayscale.png").exists()
    assert "<base64 image omitted" in (debug_dir / "request.json").read_text(encoding="utf-8")
    assert "Cat No: DEBUG 001" in (debug_dir / "raw_response.json").read_text(encoding="utf-8")
    assert "Cat No: DEBUG 001" in (debug_dir / "normalized_lines.md").read_text(encoding="utf-8")


def test_mlx_vlm_backend_writes_debug_artifacts_when_service_fails(tmp_path: Path) -> None:
    def requester(_url: str, _payload: dict[str, object], _headers: dict[str, str], _timeout: float) -> object:
        raise OcrBackendUnavailableError("service unavailable")

    backend = MlxVlmOcrBackend(
        service_url="http://ocr-service:8111",
        prompt="extract text",
        debug_output_dir=tmp_path,
        requester=requester,
    )

    with pytest.raises(OcrBackendUnavailableError):
        backend.extract(_build_prepared_image(width=1200, height=800))

    debug_dir = tmp_path / "label_digest" / "ocr" / "mlx_vlm"
    assert (debug_dir / "input.png").exists()
    assert "service unavailable" in (debug_dir / "error.json").read_text(encoding="utf-8")
    assert "<base64 image omitted" in (debug_dir / "request.json").read_text(encoding="utf-8")


def test_mlx_vlm_backend_requires_service_url() -> None:
    backend = MlxVlmOcrBackend(service_url=None, prompt="extract text")

    with pytest.raises(OcrBackendUnavailableError, match="IDENTIFY_MLX_VLM_SERVICE_URL"):
        backend.extract(_build_prepared_image(width=1200, height=800))


def test_paddleocr_backend_normalizes_pipeline_output() -> None:
    pipeline = FakePaddleOcrPipeline(
        [
            {
                "rec_texts": ["Cat No: TOVRI 001", "Boards of Canada"],
                "rec_scores": [0.98, 0.91],
                "rec_polys": [
                    [[0, 0], [10, 0], [10, 10], [0, 10]],
                    [[0, 20], [50, 20], [50, 30], [0, 30]],
                ],
            }
        ]
    )
    backend = PaddleOcrVlBackend(
        max_image_dimension=320,
        variant_names=("grayscale",),
        pipeline_factory=lambda: pipeline,
    )

    result = backend.extract(_build_prepared_image(width=1200, height=800))

    assert result.source == "paddleocr_vl"
    assert result.raw_text == "Cat No: TOVRI 001\nBoards of Canada"
    assert result.lines[0].confidence == 0.98
    assert result.lines[0].box == ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))
    assert Path(pipeline.inputs[0]).suffix == ".png"


def test_paddleocr_backend_deduplicates_nested_text() -> None:
    pipeline = FakePaddleOcrPipeline(
        {
            "text": "Cat No: TOVRI 001",
            "blocks": [
                {"content": "Cat No: TOVRI 001", "confidence": 0.8},
                {"content": "Warp Records", "bbox": [1, 2, 11, 12]},
            ],
        }
    )
    backend = PaddleOcrVlBackend(pipeline_factory=lambda: pipeline)

    result = backend.extract(_build_prepared_image(width=1200, height=800))

    assert [line.text for line in result.lines] == ["Cat No: TOVRI 001", "Warp Records"]
    assert result.lines[1].box == ((1.0, 2.0), (11.0, 2.0), (11.0, 12.0), (1.0, 12.0))


def test_paddleocr_backend_writes_native_debug_artifacts(tmp_path: Path) -> None:
    debug_result = FakePaddleDebugResult()
    backend = PaddleOcrVlBackend(
        debug_output_dir=tmp_path,
        pipeline_factory=lambda: FakePaddleOcrPipeline([debug_result]),
    )

    result = backend.extract(_build_prepared_image(width=1200, height=800))

    assert result.raw_text == "Cat No: DEBUG 001"
    assert debug_result.print_called
    assert {kind for kind, _path in debug_result.save_paths} == {"json", "markdown", "image"}
    debug_dir = tmp_path / "label_digest" / "ocr" / "paddleocr_vl"
    assert (debug_dir / "input.png").exists()
    assert (debug_dir / "paddle_result_01" / "debug.json").exists()
    assert "Cat No: DEBUG 001" in (debug_dir / "normalized_lines.json").read_text(encoding="utf-8")


def test_paddleocr_backend_raises_unavailable_when_package_is_missing() -> None:
    backend = PaddleOcrVlBackend(pipeline_factory=lambda: (_ for _ in ()).throw(ImportError("missing")))

    with pytest.raises(OcrBackendUnavailableError):
        backend.extract(_build_prepared_image(width=1200, height=800))


def test_paddleocr_backend_reports_nested_import_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    ocr_backends._PADDLEOCR_PIPELINE_CACHE.clear()  # noqa: SLF001
    ocr_backends._PADDLEOCR_VL_CLASS = None  # noqa: SLF001

    real_import = builtins.__import__

    def fail_nested_paddle_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "paddleocr":
            raise ImportError("No module named 'paddlex'", name="paddlex")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_nested_paddle_import)
    backend = PaddleOcrVlBackend(vl_rec_server_url="http://localhost:8111/")

    try:
        with pytest.raises(OcrBackendUnavailableError, match="paddlex"):
            backend.extract(_build_prepared_image(width=1200, height=800))
    finally:
        ocr_backends._PADDLEOCR_PIPELINE_CACHE.clear()  # noqa: SLF001
        ocr_backends._PADDLEOCR_VL_CLASS = None  # noqa: SLF001


def test_paddleocr_backend_times_out() -> None:
    backend = PaddleOcrVlBackend(
        timeout_seconds=0.001,
        pipeline_factory=SlowPaddleOcrPipeline,
    )

    with pytest.raises(OcrBackendTimeoutError):
        backend.extract(_build_prepared_image(width=1200, height=800))


def test_paddleocr_backend_reuses_process_pipeline_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    created_pipelines: list[dict[str, object]] = []

    class FakePaddleOCRVL:
        def __init__(self, **kwargs: object) -> None:
            created_pipelines.append(kwargs)

        def predict(self, *, input: str) -> object:
            del input
            return {"rec_texts": ["Cat No: CACHE 001"]}

    fake_paddleocr = types.ModuleType("paddleocr")
    fake_paddleocr.PaddleOCRVL = FakePaddleOCRVL
    monkeypatch.setitem(sys.modules, "paddleocr", fake_paddleocr)
    ocr_backends._PADDLEOCR_VL_CLASS = None  # noqa: SLF001
    ocr_backends._PADDLEOCR_PIPELINE_CACHE.clear()  # noqa: SLF001

    try:
        first_backend = PaddleOcrVlBackend(vl_rec_server_url="http://localhost:8111/")
        second_backend = PaddleOcrVlBackend(vl_rec_server_url="http://localhost:8111/")

        first_result = first_backend.extract(_build_prepared_image(width=1200, height=800))
        second_result = second_backend.extract(_build_prepared_image(width=1200, height=800))
    finally:
        ocr_backends._PADDLEOCR_PIPELINE_CACHE.clear()  # noqa: SLF001
        ocr_backends._PADDLEOCR_VL_CLASS = None  # noqa: SLF001

    assert first_result.raw_text == "Cat No: CACHE 001"
    assert second_result.raw_text == "Cat No: CACHE 001"
    assert len(created_pipelines) == 1


def test_paddleocr_backend_reuses_imported_class_without_second_import(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePaddleOCRVL:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def predict(self, *, input: str) -> object:
            del input
            return {"rec_texts": ["Cat No: IMPORT 001"]}

    fake_paddleocr = types.ModuleType("paddleocr")
    fake_paddleocr.PaddleOCRVL = FakePaddleOCRVL
    monkeypatch.setitem(sys.modules, "paddleocr", fake_paddleocr)
    ocr_backends._PADDLEOCR_PIPELINE_CACHE.clear()  # noqa: SLF001
    ocr_backends._PADDLEOCR_VL_CLASS = None  # noqa: SLF001

    real_import = builtins.__import__

    def fail_paddleocr_reimport(name: str, *args: object, **kwargs: object) -> object:
        if name == "paddleocr":
            raise RuntimeError("PDX has already been initialized. Reinitialization is not supported.")
        return real_import(name, *args, **kwargs)

    try:
        first_backend = PaddleOcrVlBackend(vl_rec_server_url="http://localhost:8111/a")
        second_backend = PaddleOcrVlBackend(vl_rec_server_url="http://localhost:8111/b")

        assert first_backend.extract(_build_prepared_image(width=1200, height=800)).raw_text == "Cat No: IMPORT 001"
        monkeypatch.setattr(builtins, "__import__", fail_paddleocr_reimport)
        assert second_backend.extract(_build_prepared_image(width=1200, height=800)).raw_text == "Cat No: IMPORT 001"
    finally:
        ocr_backends._PADDLEOCR_PIPELINE_CACHE.clear()  # noqa: SLF001
        ocr_backends._PADDLEOCR_VL_CLASS = None  # noqa: SLF001


def test_ocr_cascade_returns_primary_result_without_evidence_based_fallback() -> None:
    noisy_lines = tuple(
        OcrTextLine(text=f"NOISE {index} CAT001", confidence=None, source="tesseract") for index in range(41)
    )
    primary = StubOcrBackend(
        OcrResult(
            source="tesseract",
            raw_text="\n".join(line.text for line in noisy_lines),
            lines=noisy_lines,
        )
    )
    fallback = StubOcrBackend(
        OcrResult(
            source="paddleocr_vl",
            raw_text="REAL LABEL CAT002",
            lines=(OcrTextLine(text="REAL LABEL CAT002", confidence=0.9, source="paddleocr_vl"),),
        )
    )
    cascade = OcrCascade(primary_backend=primary, fallback_backend=fallback)

    result = cascade.extract(_build_prepared_image(width=1200, height=800))

    assert result.source == "tesseract"
    assert fallback.calls == 0


def test_ocr_cascade_runs_fallback_when_primary_result_is_empty() -> None:
    primary = StubOcrBackend(OcrResult(source="mlx_vlm", raw_text="", lines=()))
    fallback = StubOcrBackend(
        OcrResult(
            source="tesseract",
            raw_text="FDMTL2",
            lines=(OcrTextLine("FDMTL2", None, "tesseract"),),
        )
    )
    cascade = OcrCascade(primary_backend=primary, fallback_backend=fallback)

    result = cascade.extract(_build_prepared_image(width=1200, height=800))

    assert result.raw_text == "FDMTL2"
    assert primary.calls == 1
    assert fallback.calls == 1


def test_ocr_cascade_runs_fallback_when_primary_backend_is_unavailable() -> None:
    primary = FailingOcrBackend()
    fallback = StubOcrBackend(
        OcrResult(
            source="tesseract",
            raw_text="Cat No: TOVRI 001",
            lines=(OcrTextLine(text="Cat No: TOVRI 001", confidence=None, source="tesseract"),),
        )
    )
    cascade = OcrCascade(primary_backend=primary, fallback_backend=fallback)

    result = cascade.extract(_build_prepared_image(width=1200, height=800))

    assert result.source == "tesseract"
    assert primary.calls == 1
    assert fallback.calls == 1


def test_ocr_cascade_reraises_primary_error_without_fallback() -> None:
    cascade = OcrCascade(primary_backend=FailingOcrBackend())

    with pytest.raises(OcrBackendUnavailableError):
        cascade.extract(_build_prepared_image(width=1200, height=800))


def test_build_default_ocr_cascade_routes_paddleocr_to_tesseract_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "identify_ocr_backend", "paddleocr_vl")
    monkeypatch.setattr(settings, "identify_ocr_tesseract_fallback_enabled", True)
    monkeypatch.setattr(ocr_backends, "PaddleOcrVlBackend", _build_unavailable_paddle_backend)
    cascade = ocr_backends.build_default_ocr_cascade(StubOcrExtractor())

    result = cascade.extract(_build_prepared_image(width=1200, height=800))

    assert result.source == "tesseract"
    assert result.raw_text == "Cat No: TOVRI 001"


def test_build_default_ocr_cascade_routes_auto_to_mlx_service_with_tesseract_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "identify_ocr_backend", "auto")
    monkeypatch.setattr(settings, "identify_ocr_tesseract_fallback_enabled", True)
    monkeypatch.setattr(settings, "identify_mlx_vlm_service_url", "http://ocr-service:8111")
    monkeypatch.setattr(ocr_backends, "MlxVlmOcrBackend", _build_unavailable_mlx_backend)
    cascade = ocr_backends.build_default_ocr_cascade(StubOcrExtractor())

    result = cascade.extract(_build_prepared_image(width=1200, height=800))

    assert result.source == "tesseract"
    assert result.raw_text == "Cat No: TOVRI 001"


def _build_prepared_image(
    *,
    width: int,
    height: int,
    variant_names: tuple[str, ...] = ("grayscale",),
) -> PreparedImage:
    return PreparedImage(
        filename="label.jpg",
        content_type="image/jpeg",
        data=b"image-data",
        size_bytes=10,
        digest="digest",
        width=width,
        height=height,
        variants=tuple(
            ImageVariant(name=variant_name, data=_build_image_bytes(width=width, height=height))
            for variant_name in variant_names
        ),
    )


def _build_image_bytes(*, width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height), color=(255, 255, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
