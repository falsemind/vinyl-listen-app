from fastapi.testclient import TestClient

from app.main import app
from app.services.discogs_service import DiscogsClientError


def test_import_release_endpoint_returns_created_release_id(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    override_release_import_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/releases/import",
            json={"discogs_release_id": 555123},
        )

    assert response.status_code == 201
    assert response.json() == {
        "release_id": "release-123",
        "discogs_release_id": 555123,
        "status": "created",
    }
    assert service.import_calls == [(555123, False)]


def test_import_release_endpoint_returns_404_for_missing_discogs_release(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    service.import_error = DiscogsClientError("Discogs API error (404): release not found")
    override_release_import_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/releases/import",
            json={"discogs_release_id": 999999},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Discogs API error (404): release not found"}


def test_import_release_endpoint_sanitizes_request_validation_errors(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    override_release_import_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/releases/import",
            json={"discogs_release_id": "not-an-integer"},
        )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_request",
            "message": "Input should be a valid integer, unable to parse string as an integer",
        }
    }


def test_get_release_endpoint_returns_local_release_metadata(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    override_release_import_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/releases/release-123")

    assert response.status_code == 200
    assert response.json() == {
        "id": "release-123",
        "discogs_release_id": 555123,
        "artist": "Boards of Canada",
        "title": "Music Has The Right To Children",
        "year": 1998,
        "label": "Warp Records",
        "catalog_number": "WARPLP55",
        "barcode": "5021603065515",
        "genres": ["Electronic"],
        "styles": ["IDM"],
        "cover_image_url": "https://img.discogs.com/cover.jpg",
        "created_at": "2026-04-19T00:00:00Z",
        "updated_at": "2026-04-19T00:00:00Z",
    }
    assert service.lookup_calls == ["release-123"]


def test_get_release_endpoint_returns_404_when_release_missing(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    override_release_import_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/releases/missing-release")

    assert response.status_code == 404
    assert response.json() == {"detail": "Release 'missing-release' was not found."}
