import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

pytest_plugins = [
    "tests.fixtures.api_stubs",
    "tests.fixtures.discogs_service",
    "tests.fixtures.identify_service",
    "tests.fixtures.release_import_service",
    "tests.fixtures.sessions_service",
]


@pytest.fixture(autouse=True)
def default_api_auth_override(request):
    if request.node.get_closest_marker("real_auth") is not None:
        yield
        return

    from app.api.auth_dependencies import require_authenticated_user
    from app.main import app

    app.dependency_overrides[require_authenticated_user] = lambda: SimpleNamespace(
        account=SimpleNamespace(id="test-user", email="test@example.com"),
        claims=SimpleNamespace(user_id="test-user", session_id="test-session"),
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_authenticated_user, None)
