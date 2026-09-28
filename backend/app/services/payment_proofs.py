from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.config import PRIVATE_STORAGE_DIR


PROOF_STORAGE_ROOT = PRIVATE_STORAGE_DIR / "payment_proofs"
MAX_PROOF_BYTES = 10 * 1024 * 1024
PROOF_CHUNK_BYTES = 1024 * 1024


def payment_proof_directory(payment_id: UUID) -> Path:
    return PROOF_STORAGE_ROOT / str(payment_id)


def payment_proof_path(payment_id: UUID, filename: str) -> Path:
    return payment_proof_directory(payment_id) / filename


def ensure_receipt_file_name(filename: str) -> str:
    safe_name = Path(filename).name.strip()
    if not safe_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Receipt file must have a name",
        )
    if len(safe_name) > 150:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Receipt file name is too long",
        )
    return safe_name


def receipt_extension(signature: bytes) -> str | None:
    """Detect the supported format from bytes, never from a client MIME type."""
    if signature.startswith(b"%PDF-"):
        return ".pdf"
    if signature.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if signature.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if signature.startswith(b"RIFF") and signature[8:12] == b"WEBP":
        return ".webp"
    return None


def store_validated_receipt(
    upload: UploadFile,
    target_directory: Path,
    *,
    target_stem: str = "proof",
) -> tuple[Path, str]:
    """Store one validated PDF/image and return its path and safe source name."""
    safe_name = ensure_receipt_file_name(upload.filename or "")
    target_directory.mkdir(parents=True, exist_ok=True)
    temporary_path = target_directory / f".upload-{uuid4().hex}.tmp"
    total_bytes = 0
    signature = b""

    try:
        with temporary_path.open("wb") as target_file:
            while chunk := upload.file.read(PROOF_CHUNK_BYTES):
                total_bytes += len(chunk)
                if total_bytes > MAX_PROOF_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Payment proof cannot exceed 10 MB",
                    )
                if len(signature) < 16:
                    signature += chunk[: 16 - len(signature)]
                target_file.write(chunk)

        if total_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment proof is empty",
            )
        extension = receipt_extension(signature)
        if extension is None:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Payment proof must be a PDF, JPEG, PNG, or WebP file",
            )
        target_path = target_directory / f"{target_stem}{extension}"
        temporary_path.replace(target_path)
        return target_path, safe_name
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
