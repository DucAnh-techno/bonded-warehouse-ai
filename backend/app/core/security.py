import hashlib
from pathlib import Path
from typing import Set

ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".xlsx", ".xls"}
MAX_FILE_BYTES: int = 25 * 1024 * 1024  # 25 MB


def calculate_sha256(file_bytes: bytes) -> str:
    """Calculate deterministic SHA-256 checksum of raw file bytes."""
    hasher = hashlib.sha256()
    hasher.update(file_bytes)
    return hasher.hexdigest()


def is_allowed_file_extension(filename: str) -> bool:
    """Validate that file extension is among permitted types."""
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


def sanitize_filename(filename: str) -> str:
    """Extract safe basename to prevent path traversal attacks on Windows/Linux."""
    return Path(filename).name
