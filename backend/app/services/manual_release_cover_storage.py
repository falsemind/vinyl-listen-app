from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


@dataclass(frozen=True)
class StoredManualReleaseCover:
    storage_key: str
    image_url: str
    thumbnail_url: str


class ManualReleaseCoverStorage:
    """Store manual release cover images on the local filesystem."""

    def __init__(self, root_dir: Path, public_url_prefix: str) -> None:
        self.root_dir = root_dir
        self.public_url_prefix = public_url_prefix.rstrip("/")

    def store_draft_cover(
        self,
        *,
        user_id: str,
        draft_id: str,
        content_type: str,
        image_bytes: bytes,
    ) -> StoredManualReleaseCover:
        extension = _cover_extension(content_type)
        filename = f"cover{extension}"
        target_dir = self.root_dir / user_id / draft_id
        target_dir.mkdir(parents=True, exist_ok=True)

        for existing_file in target_dir.glob("cover.*"):
            if existing_file.name != filename:
                existing_file.unlink(missing_ok=True)

        target_path = target_dir / filename
        target_path.write_bytes(image_bytes)

        storage_key = f"manual-release-covers/{user_id}/{draft_id}/{filename}"
        public_url = (
            f"{self.public_url_prefix}/{quote(user_id, safe='')}/"
            f"{quote(draft_id, safe='')}/{quote(filename, safe='')}"
        )
        return StoredManualReleaseCover(
            storage_key=storage_key,
            image_url=public_url,
            thumbnail_url=public_url,
        )


def _cover_extension(content_type: str) -> str:
    match content_type.strip().lower():
        case "image/jpeg":
            return ".jpg"
        case "image/png":
            return ".png"
        case "image/webp":
            return ".webp"
        case _:
            raise ValueError(f"Unsupported manual release cover content type: {content_type}")
