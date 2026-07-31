import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import AETHER_POSTAL_CODES_PATH
from app.schemas.postal_code import PostalCodeRead

router = APIRouter(prefix="/api/v1/postal-codes", tags=["postal codes"])

CATALOG_PATH = Path(AETHER_POSTAL_CODES_PATH)


@lru_cache(maxsize=1)
def load_postal_code_catalog() -> tuple[PostalCodeRead, ...]:
    if not CATALOG_PATH.is_file():
        raise FileNotFoundError(CATALOG_PATH)

    raw_entries = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return tuple(
        PostalCodeRead(
            postal_code=str(entry["postal_code"]).strip().zfill(5),
            state=str(entry["state"]).strip(),
            municipality=str(entry["municipality"]).strip(),
            city=str(entry["city"]).strip(),
            settlement_type=str(entry["settlement_type"]).strip(),
            settlement_name=str(entry["settlement_name"]).strip(),
        )
        for entry in raw_entries
    )


@router.get("", response_model=list[PostalCodeRead])
def list_postal_codes(
    q: Annotated[
        str,
        Query(
            min_length=2,
            max_length=5,
            pattern=r"^\d{2,5}$",
            description="Postal code prefix or exact code",
        ),
    ],
) -> list[PostalCodeRead]:
    try:
        catalog = load_postal_code_catalog()
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Postal code catalog is unavailable",
        ) from error

    normalized_query = q.strip()
    matches = [
        entry
        for entry in catalog
        if entry.postal_code.startswith(normalized_query)
    ]
    matches.sort(
        key=lambda entry: (
            entry.postal_code,
            entry.settlement_name,
            entry.settlement_type,
        )
    )
    return matches[:100]