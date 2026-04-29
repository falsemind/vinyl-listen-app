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
