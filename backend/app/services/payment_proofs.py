from __future__ import annotations

from pathlib import Path
from uuid import UUID


PROOF_STORAGE_ROOT = (
    Path(__file__).resolve().parents[2] / "private_storage" / "payment_proofs"
)


def payment_proof_directory(payment_id: UUID) -> Path:
    return PROOF_STORAGE_ROOT / str(payment_id)


def payment_proof_path(payment_id: UUID, filename: str) -> Path:
    return payment_proof_directory(payment_id) / filename
