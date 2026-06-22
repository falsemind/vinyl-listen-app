import pytest

from app.services.manual_release_policy import (
    MAX_MANUAL_RELEASE_COVER_BYTES,
    MAX_MANUAL_RELEASE_COVER_LONGEST_SIDE_PX,
    MAX_MANUAL_RELEASE_DRAFTS,
    MIN_MANUAL_RELEASE_COVER_LONGEST_SIDE_PX,
    ManualReleaseCoverValidationError,
    ManualReleaseDraftLimitExceeded,
    ensure_manual_release_draft_capacity,
    validate_manual_release_cover_dimensions,
    validate_manual_release_cover_policy,
)


def test_ensure_manual_release_draft_capacity_allows_room_for_another_draft() -> None:
    ensure_manual_release_draft_capacity(MAX_MANUAL_RELEASE_DRAFTS - 1)


def test_ensure_manual_release_draft_capacity_rejects_limit() -> None:
    with pytest.raises(ManualReleaseDraftLimitExceeded):
        ensure_manual_release_draft_capacity(MAX_MANUAL_RELEASE_DRAFTS)


def test_ensure_manual_release_draft_capacity_rejects_negative_count() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        ensure_manual_release_draft_capacity(-1)


def test_validate_manual_release_cover_policy_allows_supported_file_at_limit() -> None:
    validate_manual_release_cover_policy(" IMAGE/PNG ", MAX_MANUAL_RELEASE_COVER_BYTES)


def test_validate_manual_release_cover_policy_rejects_unsupported_content_type() -> None:
    with pytest.raises(ManualReleaseCoverValidationError, match="JPEG, PNG, or WebP"):
        validate_manual_release_cover_policy("image/gif", 1024)


def test_validate_manual_release_cover_policy_rejects_file_over_limit() -> None:
    with pytest.raises(ManualReleaseCoverValidationError, match="500 KB or smaller"):
        validate_manual_release_cover_policy("image/jpeg", MAX_MANUAL_RELEASE_COVER_BYTES + 1)


def test_validate_manual_release_cover_dimensions_allows_longest_side_bounds() -> None:
    validate_manual_release_cover_dimensions(
        MIN_MANUAL_RELEASE_COVER_LONGEST_SIDE_PX,
        MAX_MANUAL_RELEASE_COVER_LONGEST_SIDE_PX,
    )


def test_validate_manual_release_cover_dimensions_rejects_too_small_longest_side() -> None:
    with pytest.raises(ManualReleaseCoverValidationError, match="at least 100 px"):
        validate_manual_release_cover_dimensions(MIN_MANUAL_RELEASE_COVER_LONGEST_SIDE_PX - 1, 80)


def test_validate_manual_release_cover_dimensions_rejects_too_large_longest_side() -> None:
    with pytest.raises(ManualReleaseCoverValidationError, match="1200 px or smaller"):
        validate_manual_release_cover_dimensions(MAX_MANUAL_RELEASE_COVER_LONGEST_SIDE_PX + 1, 100)
