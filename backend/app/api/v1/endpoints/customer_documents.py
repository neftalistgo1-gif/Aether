from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.endpoints.customers import find_customer_or_404
from app.db.session import get_db
from app.models.customer_document import CustomerDocument
from app.schemas.customer_document import CustomerDocumentRead
from app.services.audit import record_audit_event
from app.services.customer_documents import customer_documents_directory, store_customer_document

router = APIRouter(prefix="/api/v1/customers/{customer_id}/documents", tags=["customer-documents"])


@router.get("", response_model=list[CustomerDocumentRead])
def list_customer_documents(customer_id: UUID, db: Session = Depends(get_db)) -> list[CustomerDocument]:
    find_customer_or_404(customer_id, db)
    return list(db.scalars(select(CustomerDocument).where(CustomerDocument.customer_id == customer_id).order_by(CustomerDocument.created_at.desc())))


@router.post("", response_model=CustomerDocumentRead, status_code=status.HTTP_201_CREATED)
def upload_customer_document(
    customer_id: UUID,
    document_type: str = Form(),
    uploaded_by: str = Form(),
    file: UploadFile = File(),
    db: Session = Depends(get_db),
) -> CustomerDocument:
    find_customer_or_404(customer_id, db)
    if document_type not in {"ine", "comprobante_domicilio", "otro"}:
        raise HTTPException(status_code=422, detail="Tipo de documento no válido")
    if not uploaded_by.strip():
        raise HTTPException(status_code=422, detail="Falta quien sube el documento")
    original_name, storage_name, size_bytes = store_customer_document(customer_id, file)
    document = CustomerDocument(customer_id=customer_id, document_type=document_type, original_name=original_name, storage_name=storage_name, media_type=file.content_type or "application/octet-stream", size_bytes=size_bytes, uploaded_by=uploaded_by.strip())
    db.add(document)
    db.flush()
    record_audit_event(db, actor=document.uploaded_by, action="customer.document_uploaded", entity_type="CustomerDocument", entity_id=document.id, reason="Customer document uploaded", after_data={"customer_id": str(customer_id), "document_type": document_type, "original_name": original_name})
    db.commit()
    db.refresh(document)
    return document


@router.get("/{document_id}/download")
def download_customer_document(customer_id: UUID, document_id: UUID, db: Session = Depends(get_db)):
    document = db.scalar(select(CustomerDocument).where(CustomerDocument.id == document_id, CustomerDocument.customer_id == customer_id))
    if document is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    path = customer_documents_directory(customer_id) / Path(document.storage_name).name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="El archivo ya no está disponible")
    return FileResponse(path, media_type=document.media_type, filename=document.original_name)
