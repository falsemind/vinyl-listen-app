from dataclasses import dataclass

MAX_MANUAL_RELEASE_DRAFTS = 5
MAX_MANUAL_RELEASE_COVER_BYTES = 500 * 1024
MIN_MANUAL_RELEASE_COVER_LONGEST_SIDE_PX = 100
MAX_MANUAL_RELEASE_COVER_LONGEST_SIDE_PX = 1200

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
MIN_RELEASE_YEAR = 1900
MAX_RELEASE_YEAR = 2100
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
        raise ManualReleaseCoverValidationError("Cover image must be 500 KB or smaller.")


def validate_manual_release_cover_dimensions(width_px: int, height_px: int) -> None:
    """Validate cover image dimensions for manual releases."""
    if width_px <= 0 or height_px <= 0:
        raise ManualReleaseCoverValidationError("Cover image dimensions could not be detected.")

    longest_side_px = max(width_px, height_px)
    if longest_side_px < MIN_MANUAL_RELEASE_COVER_LONGEST_SIDE_PX:
        raise ManualReleaseCoverValidationError("Cover image longest side must be at least 100 px.")
    if longest_side_px > MAX_MANUAL_RELEASE_COVER_LONGEST_SIDE_PX:
        raise ManualReleaseCoverValidationError("Cover image longest side must be 1200 px or smaller.")
