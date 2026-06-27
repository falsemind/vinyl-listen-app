from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4


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
        filename = f"cover-{uuid4().hex}{extension}"
        target_dir = self.root_dir / user_id / draft_id
        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = target_dir / filename
        temp_path = target_dir / f".{filename}.tmp"
        try:
            temp_path.write_bytes(image_bytes)
            temp_path.replace(target_path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

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

    def store_release_cover(
        self,
        *,
        user_id: str,
        release_id: str,
        content_type: str,
        image_bytes: bytes,
    ) -> StoredManualReleaseCover:
        return self._store_cover(
            user_id=user_id,
            resource_id=release_id,
            content_type=content_type,
            image_bytes=image_bytes,
        )

    def delete_stored_cover(self, storage_key: str | None) -> None:
        if not storage_key:
            return
        path = self._path_for_storage_key(storage_key)
        if path is not None:
            path.unlink(missing_ok=True)

    def cleanup_draft_covers(self, *, user_id: str, draft_id: str, keep_storage_key: str | None) -> None:
        target_dir = self.root_dir / user_id / draft_id
        if not target_dir.exists():
            return

        keep_path = self._path_for_storage_key(keep_storage_key)
        for pattern in ("cover-*.*", "cover.*"):
            for existing_file in target_dir.glob(pattern):
                if keep_path is None or existing_file != keep_path:
                    existing_file.unlink(missing_ok=True)
        for temp_file in target_dir.glob(".cover-*.tmp"):
            temp_file.unlink(missing_ok=True)

    def _store_cover(
        self,
        *,
        user_id: str,
        resource_id: str,
        content_type: str,
        image_bytes: bytes,
    ) -> StoredManualReleaseCover:
        extension = _cover_extension(content_type)
        filename = f"cover-{uuid4().hex}{extension}"
        target_dir = self.root_dir / user_id / resource_id
        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = target_dir / filename
        temp_path = target_dir / f".{filename}.tmp"
        try:
            temp_path.write_bytes(image_bytes)
            temp_path.replace(target_path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

        storage_key = f"manual-release-covers/{user_id}/{resource_id}/{filename}"
        public_url = (
            f"{self.public_url_prefix}/{quote(user_id, safe='')}/"
            f"{quote(resource_id, safe='')}/{quote(filename, safe='')}"
        )
        return StoredManualReleaseCover(
            storage_key=storage_key,
            image_url=public_url,
            thumbnail_url=public_url,
        )

    def _path_for_storage_key(self, storage_key: str | None) -> Path | None:
        if not storage_key:
            return None
        prefix = "manual-release-covers/"
        if not storage_key.startswith(prefix):
            return None
        relative_key = storage_key.removeprefix(prefix)
        parts = Path(relative_key).parts
        if len(parts) != 3 or any(part in {"", ".", ".."} for part in parts):
            return None
        return self.root_dir.joinpath(*parts)


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
