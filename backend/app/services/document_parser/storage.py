import uuid
from pathlib import Path
from typing import Tuple, Optional
from fastapi import UploadFile
from app.core.config import settings
from app.core.security import calculate_sha256, is_allowed_file_extension, sanitize_filename


class StorageService:
    """
    Manages byte-for-byte immutable document preservation in data/uploads/.
    Guarantees original files are never altered, compressed lossily, or overwritten.
    """

    def __init__(self, upload_dir: Path = settings.UPLOAD_DIR):
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_uploaded_file(
        self, upload_file: UploadFile
    ) -> Tuple[str, str, int, str, Optional[int]]:
        """
        Saves uploaded file preserving original bytes.
        Returns: (stored_relative_path, original_filename, file_size, sha256_hash, page_count)
        page_count is populated for PDF files only; None for Excel/image files.
        """
        original_name = sanitize_filename(upload_file.filename or "unknown_doc")
        if not is_allowed_file_extension(original_name):
            raise ValueError(
                f"Loại tệp không được hỗ trợ: '{original_name}'. "
                "Chỉ chấp nhận PDF, XLSX, XLS, PNG, JPG, TIFF."
            )

        content = await upload_file.read(settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024 + 1)
        file_size = len(content)
        if file_size == 0:
            raise ValueError("Tệp tải lên rỗng (0 bytes). Vui lòng kiểm tra lại.")
        if file_size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise ValueError(
                f"Kích thước tệp ({file_size // (1024*1024)} MB) vượt quá giới hạn "
                f"{settings.MAX_UPLOAD_SIZE_MB} MB."
            )

        sha256_hash = calculate_sha256(content)

        # Deterministic storage name preserving original extension
        suffix = Path(original_name).suffix.lower()
        unique_storage_name = f"{uuid.uuid4().hex}{suffix}"
        target_path = self.upload_dir / unique_storage_name

        with open(target_path, "wb") as f:
            f.write(content)

        # Detect page count for PDF files using PyMuPDF
        page_count: Optional[int] = None
        if suffix == ".pdf":
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(stream=content, filetype="pdf")
                page_count = doc.page_count
                doc.close()
            except Exception:
                # Corrupted PDF: remove the file and raise
                try:
                    target_path.unlink(missing_ok=True)
                except Exception:
                    pass
                raise ValueError(
                    "Tệp PDF không hợp lệ hoặc bị hỏng. Vui lòng kiểm tra lại tệp."
                )
        elif suffix in (".xlsx", ".xls"):
            # Validate Excel files are readable
            try:
                if suffix == ".xlsx":
                    import openpyxl
                    wb = openpyxl.load_workbook(
                        filename=target_path, read_only=True, data_only=False
                    )
                    wb.close()
                else:
                    import xlrd
                    xlrd.open_workbook(file_contents=content)
            except Exception:
                try:
                    target_path.unlink(missing_ok=True)
                except Exception:
                    pass
                raise ValueError(
                    "Tệp Excel không hợp lệ hoặc bị hỏng. Vui lòng kiểm tra lại tệp."
                )

        # Store the absolute path (using forward slashes for cross-platform compatibility)
        absolute_path = str(target_path.resolve()).replace("\\", "/")
        return absolute_path, original_name, file_size, sha256_hash, page_count

    def get_absolute_path(self, stored_path: str) -> Path:
        """Return absolute Path from stored path (stored as absolute string)."""
        return Path(stored_path)


storage_service = StorageService()
