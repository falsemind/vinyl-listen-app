from fastapi.testclient import TestClient

from app.api.routes.identify import get_identify_service
from app.main import app
from app.schemas.identify import IdentifyJobStatus
from app.services.entitlement_service import FeatureGateError
from app.services.identify_job_service import IdentifyCapacityExceededError, IdentifyJobNotFoundError
from app.services.identify_service import DEFAULT_MAX_UPLOAD_SIZE_BYTES, IdentifyValidationError


def test_identify_dependency_reuses_service_instance() -> None:
    first_service = get_identify_service()
    second_service = get_identify_service()

    assert first_service is second_service


def test_identify_endpoint_returns_ranked_candidates(
    build_stub_entitlement_service,
    build_stub_identify_service,
    override_entitlement_service,
    override_identify_service,
) -> None:
    entitlement_service = build_stub_entitlement_service()
    service = build_stub_identify_service()
    override_entitlement_service(entitlement_service)
    override_identify_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/identify",
            files={"image": ("cover.jpg", b"binary-image", "image/jpeg")},
        )

    assert response.status_code == 200
    assert response.json() == {
        "candidates": [
            {
                "discogs_release_id": 555123,
                "release_id": "release-123",
                "artist": "Boards of Canada",
                "title": "Music Has The Right To Children",
                "year": 1998,
                "label": "Warp Records",
                "catalog_number": "WARPLP55",
                "barcode": "5021603065515",
                "cover_image_url": "https://img.discogs.com/cover.jpg",
                "format": "Vinyl, LP",
                "match_source": "local",
                "matched_on": ["local_lookup", "barcode"],
                "confidence": 0.733,
            }
        ]
    }
    assert service.calls == [
        {
            "size_bytes": 12,
            "filename": "cover.jpg",
            "content_type": "image/jpeg",
            "user_id": "test-user",
        }
    ]
    assert entitlement_service.calls == [
        {
            "user_id": "test-user",
            "capability": "ocr_identify",
            "units": 1,
            "event_metadata": {"source": "sync_identify"},
        }
    ]


def test_identify_endpoint_returns_structured_validation_errors(
    build_stub_entitlement_service,
    build_stub_identify_service,
    override_entitlement_service,
    override_identify_service,
) -> None:
    entitlement_service = build_stub_entitlement_service()
    service = build_stub_identify_service()
    service.error = IdentifyValidationError(
        message="Unsupported image type. Supported types: image/jpeg, image/png, image/webp.",
        status_code=415,
        code="unsupported_image_type",
    )
    override_entitlement_service(entitlement_service)
    override_identify_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/identify",
            files={"image": ("cover.gif", b"gif-binary", "image/gif")},
        )

    assert response.status_code == 415
    assert response.json() == {
        "error": {
            "code": "unsupported_image_type",
            "message": "Unsupported image type. Supported types: image/jpeg, image/png, image/webp.",
        }
    }
    assert entitlement_service.calls == []


def test_identify_endpoint_returns_feature_gate_errors(
    build_stub_entitlement_service,
    build_stub_identify_service,
    override_entitlement_service,
    override_identify_service,
) -> None:
    entitlement_service = build_stub_entitlement_service()
    entitlement_service.error = FeatureGateError(
        code="feature_usage_limit_exceeded",
        message="Usage limit reached for this feature.",
        capability="ocr_identify",
        plan="FREE",
        limit=25,
        used=25,
    )
    service = build_stub_identify_service()
    override_entitlement_service(entitlement_service)
    override_identify_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/identify",
            files={"image": ("cover.jpg", b"binary-image", "image/jpeg")},
        )

    assert response.status_code == 402
    assert response.json() == {
        "error": {
            "code": "feature_usage_limit_exceeded",
            "message": "Usage limit reached for this feature.",
            "capability": "ocr_identify",
            "plan": "FREE",
            "limit": 25,
            "used": 25,
        }
    }
    assert service.calls == []


def test_identify_endpoint_rejects_oversized_upload_before_service_call(
    build_stub_identify_service,
    override_identify_service,
) -> None:
    service = build_stub_identify_service()
    override_identify_service(service)
    oversized_image = b"x" * (DEFAULT_MAX_UPLOAD_SIZE_BYTES + 1)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/identify",
            files={"image": ("cover.jpg", oversized_image, "image/jpeg")},
        )

    assert response.status_code == 413
    assert response.json() == {
        "error": {
            "code": "image_too_large",
            "message": f"Uploaded image exceeds the {DEFAULT_MAX_UPLOAD_SIZE_BYTES} byte limit.",
        }
    }
    assert service.calls == []


def test_identify_job_endpoint_returns_accepted_status(
    build_stub_identify_job_service,
    override_identify_job_service,
) -> None:
    service = build_stub_identify_job_service()
    override_identify_job_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/identify/jobs",
            files={"image": ("cover.jpg", b"binary-image", "image/jpeg")},
        )

    assert response.status_code == 202
    assert response.json()["job_id"] == "job-123"
    assert response.json()["status"] == "upload_received"
    assert service.calls == [
        {
            "user_id": "test-user",
            "size_bytes": 12,
            "filename": "cover.jpg",
            "content_type": "image/jpeg",
        }
    ]
    assert service.process_calls == [
        {"job_id": "job-123", "size_bytes": 12, "filename": "cover.jpg", "content_type": "image/jpeg"}
    ]


def test_text_identify_job_endpoint_returns_accepted_status(
    build_stub_identify_job_service,
    override_identify_job_service,
) -> None:
    service = build_stub_identify_job_service()
    override_identify_job_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/identify/text/jobs",
            json={
                "lines": ["CAT No: SW038", "NEBULA"],
                "selected_catalog_number": "SW038",
                "source_type": "ANDROID_MLKIT_TEXT",
            },
        )

    assert response.status_code == 202
    assert response.json()["job_id"] == "job-123"
    assert response.json()["status"] == "text_received"
    assert service.calls == [
        {
            "user_id": "test-user",
            "text_lines": ["CAT No: SW038", "NEBULA"],
            "source_type": "ANDROID_MLKIT_TEXT",
        }
    ]
    assert service.process_calls == [
        {
            "job_id": "job-123",
            "text_lines": ["CAT No: SW038", "NEBULA"],
            "selected_catalog_number": "SW038",
            "selected_barcode": None,
            "source_type": "ANDROID_MLKIT_TEXT",
        }
    ]


def test_identify_job_endpoint_returns_validation_errors(
    build_stub_identify_job_service,
    override_identify_job_service,
) -> None:
    service = build_stub_identify_job_service()
    service.create_error = IdentifyValidationError(
        message="Unsupported image type. Supported types: image/jpeg, image/png, image/webp.",
        status_code=415,
        code="unsupported_image_type",
    )
    override_identify_job_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/identify/jobs",
            files={"image": ("cover.gif", b"gif-binary", "image/gif")},
        )

    assert response.status_code == 415
    assert response.json() == {
        "error": {
            "code": "unsupported_image_type",
            "message": "Unsupported image type. Supported types: image/jpeg, image/png, image/webp.",
        }
    }
    assert service.process_calls == []


def test_identify_job_endpoint_returns_capacity_errors(
    build_stub_identify_job_service,
    override_identify_job_service,
) -> None:
    service = build_stub_identify_job_service()
    service.create_error = IdentifyCapacityExceededError()
    override_identify_job_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/identify/jobs",
            files={"image": ("cover.jpg", b"binary-image", "image/jpeg")},
        )

    assert response.status_code == 429
    assert response.json() == {
        "error": {
            "code": "identify_capacity_exceeded",
            "message": "Identify capacity is full. Please retry later.",
        }
    }
    assert response.headers["Retry-After"] == "5"
    assert service.process_calls == []


def test_sync_identify_endpoint_returns_capacity_errors(
    build_stub_entitlement_service,
    build_stub_identify_service,
    build_stub_identify_job_service,
    override_entitlement_service,
    override_identify_service,
    override_identify_job_service,
) -> None:
    entitlement_service = build_stub_entitlement_service()
    identify_service = build_stub_identify_service()
    job_service = build_stub_identify_job_service()
    job_service.create_error = IdentifyCapacityExceededError()
    override_entitlement_service(entitlement_service)
    override_identify_service(identify_service)
    override_identify_job_service(job_service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/identify",
            files={"image": ("cover.jpg", b"binary-image", "image/jpeg")},
        )

    assert response.status_code == 429
    assert response.json() == {
        "error": {
            "code": "identify_capacity_exceeded",
            "message": "Identify capacity is full. Please retry later.",
        }
    }
    assert response.headers["Retry-After"] == "5"
    assert identify_service.calls == []
    assert entitlement_service.calls == []


def test_identify_job_status_endpoint_returns_job(
    build_stub_identify_job_service,
    override_identify_job_service,
) -> None:
    service = build_stub_identify_job_service()
    override_identify_job_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/identify/jobs/job-456")

    assert response.status_code == 200
    assert response.json()["job_id"] == "job-456"
    assert response.json()["status"] == "upload_received"


def test_identify_job_status_endpoint_returns_not_found(
    build_stub_identify_job_service,
    override_identify_job_service,
) -> None:
    service = build_stub_identify_job_service()
    service.get_error = IdentifyJobNotFoundError("missing")
    override_identify_job_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/identify/jobs/missing")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "identify_job_not_found",
            "message": "Identify job was not found.",
        }
    }


def test_cancel_identify_job_endpoint_requests_cancel_for_active_job(
    build_stub_identify_job_service,
    override_identify_job_service,
) -> None:
    service = build_stub_identify_job_service()
    override_identify_job_service(service)

    with TestClient(app) as client:
        response = client.post("/api/v1/identify/jobs/job-456/cancel")

    assert response.status_code == 200
    assert response.json()["job_id"] == "job-456"
    assert response.json()["status"] == "upload_received"
    assert response.json()["cancel_requested"] is True
    assert service.cancel_calls == ["job-456"]


def test_cancel_identify_job_endpoint_is_idempotent_for_canceled_job(
    build_stub_identify_job_service,
    override_identify_job_service,
) -> None:
    service = build_stub_identify_job_service()
    service.cancel_response = service.response.model_copy(
        update={
            "status": IdentifyJobStatus.CANCELED,
            "message": "Identify canceled",
            "cancel_requested": True,
        }
    )
    override_identify_job_service(service)

    with TestClient(app) as client:
        response = client.post("/api/v1/identify/jobs/job-456/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "canceled"
    assert response.json()["message"] == "Identify canceled"
    assert response.json()["cancel_requested"] is True
    assert service.cancel_calls == ["job-456"]


def test_cancel_identify_job_endpoint_noops_for_completed_job(
    build_stub_identify_job_service,
    override_identify_job_service,
) -> None:
    service = build_stub_identify_job_service()
    service.cancel_response = service.response.model_copy(
        update={
            "status": IdentifyJobStatus.COMPLETED,
            "message": "Identify completed",
            "cancel_requested": False,
        }
    )
    override_identify_job_service(service)

    with TestClient(app) as client:
        response = client.post("/api/v1/identify/jobs/job-456/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["cancel_requested"] is False
    assert service.cancel_calls == ["job-456"]


def test_cancel_identify_job_endpoint_noops_for_expired_job(
    build_stub_identify_job_service,
    override_identify_job_service,
) -> None:
    service = build_stub_identify_job_service()
    service.cancel_response = service.response.model_copy(
        update={
            "status": IdentifyJobStatus.EXPIRED,
            "message": "Identify job expired before completion. Please retry.",
            "cancel_requested": False,
        }
    )
    override_identify_job_service(service)

    with TestClient(app) as client:
        response = client.post("/api/v1/identify/jobs/job-456/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "expired"
    assert response.json()["cancel_requested"] is False
    assert service.cancel_calls == ["job-456"]


def test_cancel_identify_job_endpoint_returns_not_found(
    build_stub_identify_job_service,
    override_identify_job_service,
) -> None:
    service = build_stub_identify_job_service()
    service.cancel_error = IdentifyJobNotFoundError("missing")
    override_identify_job_service(service)

    with TestClient(app) as client:
        response = client.post("/api/v1/identify/jobs/missing/cancel")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "identify_job_not_found",
            "message": "Identify job was not found.",
        }
    }
    assert service.cancel_calls == ["missing"]
