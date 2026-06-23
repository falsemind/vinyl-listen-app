from app.main import _ensure_static_directory


def test_ensure_static_directory_creates_nested_path(tmp_path):
    target = tmp_path / "storage" / "manual-release-covers"

    _ensure_static_directory(target)

    assert target.is_dir()
