from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.config import PRIVATE_STORAGE_DIR

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024
ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


def customer_documents_directory(customer_id: UUID) -> Path:
    return PRIVATE_STORAGE_DIR / "customer_documents" / str(customer_id)


def document_extension(signature: bytes) -> tuple[str, str] | None:
    if signature.startswith(b"%PDF-"):
        return "application/pdf", ".pdf"
    if signature.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if signature.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    return None


def store_customer_document(customer_id: UUID, upload: UploadFile) -> tuple[str, str, int]:
    original_name = Path(upload.filename or "").name.strip()
    if not original_name or len(original_name) > 180:
        raise HTTPException(status_code=400, detail="El archivo debe tener un nombre válido")
    directory = customer_documents_directory(customer_id)
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / f".upload-{uuid4().hex}.tmp"
    total = 0
    signature = b""
    try:
        with temporary.open("wb") as target:
            while chunk := upload.file.read(CHUNK_BYTES):
                total += len(chunk)
                if total > MAX_DOCUMENT_BYTES:
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="El archivo no puede exceder 10 MB")
                if len(signature) < 16:
                    signature += chunk[: 16 - len(signature)]
                target.write(chunk)
        detected = document_extension(signature)
        if total == 0 or detected is None:
            raise HTTPException(status_code=415, detail="Sólo se aceptan PDF, JPG o PNG")
        media_type, extension = detected
        storage_name = f"{uuid4().hex}{extension}"
        temporary.replace(directory / storage_name)
        return original_name, storage_name, total
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
