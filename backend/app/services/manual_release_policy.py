from dataclasses import dataclass

MAX_MANUAL_RELEASE_DRAFTS = 5
MAX_MANUAL_RELEASE_COVER_BYTES = 3 * 1024 * 1024

SUPPORTED_MANUAL_RELEASE_COVER_CONTENT_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)


@dataclass(frozen=True)
class TextFieldLimit:
    """Length limits for a single manual release text field."""

    max_length: int
    min_length: int = 0


ARTIST_NAME_LIMIT = TextFieldLimit(min_length=1, max_length=200)
TITLE_LIMIT = TextFieldLimit(min_length=1, max_length=200)
LABEL_NAME_LIMIT = TextFieldLimit(min_length=1, max_length=200)
CATALOG_NUMBER_LIMIT = TextFieldLimit(max_length=80)
TRACK_TITLE_LIMIT = TextFieldLimit(min_length=1, max_length=200)
TRACK_POSITION_LIMIT = TextFieldLimit(max_length=16)
TRACK_DURATION_LIMIT = TextFieldLimit(max_length=8)
TRACK_CREDIT_NAME_LIMIT = TextFieldLimit(min_length=1, max_length=200)

MAX_MANUAL_RELEASE_ARTISTS = 20
MAX_MANUAL_RELEASE_TRACKS = 100
MIN_VINYL_DISC_COUNT = 1
MAX_VINYL_DISC_COUNT = 6

MANUAL_RELEASE_FORMATS = frozenset({"Vinyl", "CD", "Tape", "Other"})
VINYL_SIZES = frozenset({"7", "10", "12", "Other"})
VINYL_SPEEDS = frozenset({"33 1/3", "45", "78", "Other"})
TRACK_CREDIT_ROLES = frozenset({"Featuring", "Remix", "Producer", "Written-By", "Other"})


class ManualReleaseDraftLimitExceeded(ValueError):
    """Raised when a user already has the maximum number of manual drafts."""


class ManualReleaseCoverValidationError(ValueError):
    """Raised when a manual release cover fails file policy validation."""


def ensure_manual_release_draft_capacity(existing_draft_count: int) -> None:
    """Ensure a user can create one more manual release draft."""
    if existing_draft_count < 0:
        raise ValueError("existing_draft_count must be non-negative")

    if existing_draft_count >= MAX_MANUAL_RELEASE_DRAFTS:
        raise ManualReleaseDraftLimitExceeded(
            f"Manual release drafts are limited to {MAX_MANUAL_RELEASE_DRAFTS} per user."
        )


def validate_manual_release_cover_policy(content_type: str, size_bytes: int) -> None:
    """Validate cover content type and size for manual releases."""
    normalized_content_type = content_type.strip().lower()
    if normalized_content_type not in SUPPORTED_MANUAL_RELEASE_COVER_CONTENT_TYPES:
        raise ManualReleaseCoverValidationError("Cover image must be JPEG, PNG, or WebP.")

    if size_bytes < 0:
        raise ManualReleaseCoverValidationError("Cover image size must be non-negative.")

    if size_bytes > MAX_MANUAL_RELEASE_COVER_BYTES:
        raise ManualReleaseCoverValidationError("Cover image must be 3 MB or smaller.")
