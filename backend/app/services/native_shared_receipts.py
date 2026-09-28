from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile

from app.core.config import PRIVATE_STORAGE_DIR
from app.services.payment_proofs import store_validated_receipt


NATIVE_RECEIPT_STORAGE_ROOT = PRIVATE_STORAGE_DIR / "native_shared_receipts"
NATIVE_RECEIPT_TTL = timedelta(hours=24)
CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".webp": "image/webp",
}


@dataclass(frozen=True)
class StoredNativeReceipt:
    receipt_id: UUID
    filename: str
    content_type: str
    expires_at: datetime


@dataclass(frozen=True)
class ClaimedNativeReceipt:
    filename: str
    content_type: str
    content: bytes


def _receipt_directory(receipt_id: UUID, storage_root: Path) -> Path:
    return storage_root / str(receipt_id)


def _remove_receipt_directory(receipt_directory: Path) -> None:
    """Only removes known files inside one validated UUID directory."""
    for path in receipt_directory.glob("proof.*"):
        if path.is_file():
            path.unlink(missing_ok=True)
    (receipt_directory / "metadata.json").unlink(missing_ok=True)
    try:
        receipt_directory.rmdir()
    except OSError:
        pass


def cleanup_expired_native_receipts(
    *,
    storage_root: Path = NATIVE_RECEIPT_STORAGE_ROOT,
    now: datetime | None = None,
) -> None:
    if not storage_root.exists():
        return
    cutoff = (now or datetime.now(UTC)) - NATIVE_RECEIPT_TTL
    for candidate in storage_root.iterdir():
        if not candidate.is_dir():
            continue
        try:
            UUID(candidate.name)
            modified_at = datetime.fromtimestamp(
                candidate.stat().st_mtime,
                tz=UTC,
            )
        except (OSError, ValueError):
            continue
        if modified_at < cutoff:
            _remove_receipt_directory(candidate)


def store_native_shared_receipt(
    upload: UploadFile,
    *,
    user_id: UUID,
    storage_root: Path = NATIVE_RECEIPT_STORAGE_ROOT,
    now: datetime | None = None,
) -> StoredNativeReceipt:
    created_at = now or datetime.now(UTC)
    cleanup_expired_native_receipts(storage_root=storage_root, now=created_at)
    receipt_id = uuid4()
    receipt_directory = _receipt_directory(receipt_id, storage_root)

    try:
        proof_path, source_name = store_validated_receipt(
            upload,
            receipt_directory,
        )
        content_type = CONTENT_TYPES[proof_path.suffix]
        expires_at = created_at + NATIVE_RECEIPT_TTL
        metadata = {
            "user_id": str(user_id),
            "filename": source_name,
            "content_type": content_type,
            "proof_name": proof_path.name,
            "expires_at": expires_at.isoformat(),
        }
        (receipt_directory / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        _remove_receipt_directory(receipt_directory)
        raise

    return StoredNativeReceipt(
        receipt_id=receipt_id,
        filename=source_name,
        content_type=content_type,
        expires_at=expires_at,
    )


def claim_native_shared_receipt(
    receipt_id: UUID,
    *,
    user_id: UUID,
    storage_root: Path = NATIVE_RECEIPT_STORAGE_ROOT,
    now: datetime | None = None,
) -> ClaimedNativeReceipt | None:
    receipt_directory = _receipt_directory(receipt_id, storage_root)
    metadata_path = receipt_directory / "metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        expires_at = datetime.fromisoformat(metadata["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if metadata["user_id"] != str(user_id):
            return None
        if expires_at <= (now or datetime.now(UTC)):
            _remove_receipt_directory(receipt_directory)
            return None
        proof_path = receipt_directory / Path(metadata["proof_name"]).name
        if proof_path.parent != receipt_directory or not proof_path.is_file():
            return None
        content = proof_path.read_bytes()
        claimed = ClaimedNativeReceipt(
            filename=metadata["filename"],
            content_type=metadata["content_type"],
            content=content,
        )
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None

    _remove_receipt_directory(receipt_directory)
    return claimed
