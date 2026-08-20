import datetime as dt
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user, require_deal_access
from app.services import audit
from app.services.xlsx_export import build_workbook

router = APIRouter(tags=["exports"])


@router.post("/api/model-versions/{model_version_id}/exports/xlsx", status_code=status.HTTP_201_CREATED)
def export_xlsx(
    model_version_id: uuid.UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)
):
    """PRD 7.14: only approved models can be designated as official exports."""
    mv = db.get(models.ModelVersion, model_version_id)
    if mv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model version not found")
    require_deal_access(mv.deal_id, db, user)
    if mv.status != "approved":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only approved model versions can be exported.")
    if not mv.calculation_snapshot_json:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Model version has no calculated results.")

    deal = db.get(models.Deal, mv.deal_id)
    settings = get_settings()
    generated_at = dt.datetime.now(dt.timezone.utc)

    workbook_bytes = build_workbook(
        deal=schemas.DealOut.model_validate(deal).model_dump(mode="json"),
        model_version=schemas.ModelVersionOut.model_validate(mv).model_dump(mode="json"),
        scenarios=mv.calculation_snapshot_json,
        generated_at=generated_at,
    )

    os.makedirs(os.path.join(settings.storage_dir, "exports"), exist_ok=True)
    storage_key = os.path.join("exports", f"{mv.id}_{uuid.uuid4().hex}.xlsx")
    abs_path = os.path.join(settings.storage_dir, storage_key)
    with open(abs_path, "wb") as f:
        f.write(workbook_bytes)

    job = models.ExportJob(
        model_version_id=mv.id,
        export_type="xlsx",
        scenario=mv.scenario_default,
        status="complete",
        storage_key=storage_key,
        generated_at=generated_at,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    audit.record(db, entity_type="export_job", entity_id=job.id, action="export_xlsx", actor_id=user.id, deal_id=mv.deal_id)
    db.commit()
    return {"export_job_id": str(job.id), "status": job.status}


@router.get("/api/exports/{export_job_id}")
def get_export(export_job_id: uuid.UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    job = db.get(models.ExportJob, export_job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export job not found")
    mv = db.get(models.ModelVersion, job.model_version_id)
    require_deal_access(mv.deal_id, db, user)

    if job.status != "complete" or not job.storage_key:
        return {"export_job_id": str(job.id), "status": job.status, "error_message": job.error_message}

    settings = get_settings()
    abs_path = os.path.join(settings.storage_dir, job.storage_key)
    filename = f"{mv.name}_{job.export_type}.xlsx"
    return FileResponse(abs_path, filename=filename, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
