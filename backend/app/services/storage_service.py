import logging
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Tuple

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """
    Handles upload validation and local filesystem persistence.
    """

    allowed_mime_types = {
        "pdf": {"application/pdf"},
        "csv": {"text/csv", "application/csv", "application/vnd.ms-excel"},
        "xlsx": {
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
        "png": {"image/png"},
        "jpg": {"image/jpeg", "image/jpg"},
        "jpeg": {"image/jpeg", "image/jpg"},
    }

    def _upload_root(self) -> Path:
        return Path(settings.UPLOAD_DIR).resolve()

    def _user_directory(self, user_id: uuid.UUID) -> Path:
        return self._upload_root() / f"user_{user_id}"

    def _sanitize_filename(self, filename: str) -> str:
        safe_name = Path(filename).name.strip()
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", safe_name)
        return safe_name or "uploaded_file"

    def _extension(self, filename: str) -> str:
        return Path(filename).suffix.lower().lstrip(".")

    def _ensure_safe_path(self, path: Path) -> None:
        upload_root = self._upload_root()
        resolved_path = path.resolve()
        try:
            resolved_path.relative_to(upload_root)
        except ValueError as exc:
            logger.warning("Rejected unsafe upload path: %s", resolved_path)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid upload path.",
            ) from exc

    def validate_file(self, file: UploadFile) -> Tuple[str, int]:
        """
        Validates filename, extension, content type, and size.
        Returns the normalized extension and measured byte size.
        """
        if not file or not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing file.",
            )

        extension = self._extension(file.filename)
        allowed_extensions = settings.allowed_extensions
        if extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file extension. Allowed types: {', '.join(allowed_extensions)}.",
            )

        allowed_mime_types = self.allowed_mime_types.get(extension, set())
        if file.content_type and file.content_type not in allowed_mime_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file type.",
            )

        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        file.file.seek(0)

        if file_size <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        if file_size > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File too large.",
            )

        return extension, file_size

    async def save_file(self, file: UploadFile, user_id: uuid.UUID) -> Tuple[str, str, int]:
        """
        Saves a validated upload to data/uploads/user_<user_id>/.
        Returns stored filename, file path, and measured byte size.
        """
        extension, file_size = self.validate_file(file)
        original_name = self._sanitize_filename(file.filename or "uploaded_file")
        stored_filename = f"{uuid.uuid4().hex}_{original_name}"
        if not stored_filename.lower().endswith(f".{extension}"):
            stored_filename = f"{stored_filename}.{extension}"

        user_dir = self._user_directory(user_id)
        destination = user_dir / stored_filename
        self._ensure_safe_path(destination)

        user_dir.mkdir(parents=True, exist_ok=True)
        file.file.seek(0)
        try:
            with destination.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        finally:
            await file.close()

        logger.info("Stored uploaded document at %s", destination)
        return stored_filename, str(destination), file_size

    def delete_file(self, file_path: str) -> None:
        """
        Deletes a stored file when it exists and belongs to the upload root.
        Missing files are treated as already deleted.
        """
        path = Path(file_path)
        self._ensure_safe_path(path)
        if path.exists():
            path.unlink()
            logger.info("Deleted uploaded document at %s", path)


storage_service = StorageService()
