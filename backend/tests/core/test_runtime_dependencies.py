from app.core import runtime_dependencies


def test_opencv_dependency_status_is_quiet_when_feature_is_disabled(monkeypatch) -> None:
    monkeypatch.setattr(runtime_dependencies.settings, "identify_geometry_preprocess_enabled", False)
    monkeypatch.setattr(runtime_dependencies, "find_spec", lambda _name: None)

    status = runtime_dependencies._check_opencv()

    assert status.name == "opencv"
    assert not status.available
    assert not status.warn_when_unavailable


def test_opencv_dependency_status_warns_when_feature_is_enabled(monkeypatch) -> None:
    monkeypatch.setattr(runtime_dependencies.settings, "identify_geometry_preprocess_enabled", True)
    monkeypatch.setattr(runtime_dependencies, "find_spec", lambda _name: None)

    status = runtime_dependencies._check_opencv()

    assert status.name == "opencv"
    assert not status.available
    assert status.warn_when_unavailable


def test_paddleocr_dependency_status_warns_when_paddle_runtime_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(runtime_dependencies.settings, "identify_ocr_backend", "paddleocr_vl")
    monkeypatch.setattr(
        runtime_dependencies,
        "find_spec",
        lambda name: object() if name == "paddleocr" else None,
    )

    status = runtime_dependencies._check_paddleocr()

    assert status.name == "paddleocr"
    assert not status.available
    assert "paddlepaddle runtime is missing" in status.detail
    assert status.warn_when_unavailable


def test_mlx_vlm_service_config_warns_when_auto_backend_has_no_service_url(monkeypatch) -> None:
    monkeypatch.setattr(runtime_dependencies.settings, "identify_ocr_backend", "auto")
    monkeypatch.setattr(runtime_dependencies.settings, "identify_mlx_vlm_service_url", None)

    status = runtime_dependencies._check_mlx_vlm_service_config()

    assert status.name == "mlx_vlm_service"
    assert not status.available
    assert status.warn_when_unavailable


def test_paddleocr_dependency_status_is_quiet_when_auto_uses_mlx_service(monkeypatch) -> None:
    monkeypatch.setattr(runtime_dependencies.settings, "identify_ocr_backend", "auto")
    monkeypatch.setattr(runtime_dependencies, "find_spec", lambda _name: None)

    status = runtime_dependencies._check_paddleocr()

    assert status.name == "paddleocr"
    assert not status.available
    assert not status.warn_when_unavailable
