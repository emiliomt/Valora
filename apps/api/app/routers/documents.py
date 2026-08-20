import datetime as dt
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user, require_deal_access, require_editor
from app.services import audit

router = APIRouter(prefix="/api/deals/{deal_id}/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {".xlsx", ".csv", ".pdf", ".docx", ".pptx", ".txt"}


@router.post("", response_model=schemas.SourceDocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    deal_id: uuid.UUID,
    document_type: str = "other",
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    require_editor(deal_id, db, user)
    settings = get_settings()

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Supported: {sorted(ALLOWED_EXTENSIONS)}.",
        )

    content = await file.read()
    os.makedirs(os.path.join(settings.storage_dir, str(deal_id)), exist_ok=True)
    storage_key = os.path.join(str(deal_id), f"{uuid.uuid4().hex}{ext}")
    abs_path = os.path.join(settings.storage_dir, storage_key)
    with open(abs_path, "wb") as f:
        f.write(content)

    doc = models.SourceDocument(
        deal_id=deal_id,
        filename=file.filename or "unnamed",
        storage_key=storage_key,
        mime_type=file.content_type or "application/octet-stream",
        document_type=document_type,
        uploaded_by=user.id,
        processing_status="uploaded",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    audit.record(
        db,
        entity_type="source_document",
        entity_id=doc.id,
        action="upload",
        actor_id=user.id,
        deal_id=deal_id,
        new_value={"filename": doc.filename, "document_type": doc.document_type},
    )
    db.commit()
    return doc


@router.get("", response_model=list[schemas.SourceDocumentOut])
def list_documents(deal_id: uuid.UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    require_deal_access(deal_id, db, user)
    return db.query(models.SourceDocument).filter_by(deal_id=deal_id).all()
