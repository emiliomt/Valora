import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.db import get_db
from app.deps import get_current_user, require_deal_access, require_editor
from app.services import audit
from app.services.engine_bridge import build_historicals_for_deal
from app.services.importer import ImportValidationError, parse_financials_file
from app.services.taxonomy import suggest_mapping
from financial_engine.checks import check_currency_and_unit_consistency, check_no_missing_periods

router = APIRouter(prefix="/api/deals/{deal_id}/financials", tags=["financials"])


@router.post("/import", response_model=schemas.ImportResult, status_code=status.HTTP_201_CREATED)
async def import_financials(
    deal_id: uuid.UUID,
    document_id: uuid.UUID | None = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    deal = require_editor(deal_id, db, user)
    content = await file.read()
    try:
        df = parse_financials_file(file.filename or "upload.csv", content)
    except ImportValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    periods_created = 0
    line_items_created = 0
    unresolved = 0
    warnings: list[str] = []

    for fiscal_year in sorted(df["fiscal_year"].unique()):
        period = (
            db.query(models.FinancialPeriod)
            .filter_by(deal_id=deal_id, fiscal_year=int(fiscal_year), period_type="annual")
            .first()
        )
        if period is None:
            period = models.FinancialPeriod(
                deal_id=deal_id, fiscal_year=int(fiscal_year), period_type="annual", is_historical=True
            )
            db.add(period)
            db.flush()
            periods_created += 1

        year_rows = df[df["fiscal_year"] == fiscal_year]
        for _, row in year_rows.iterrows():
            normalized_key, confidence = suggest_mapping(row["label"], statement_hint=row["statement_type"])
            if normalized_key is None:
                unresolved += 1
                warnings.append(f"FY{int(fiscal_year)}: could not auto-map '{row['label']}'")

            line_item = models.FinancialLineItem(
                deal_id=deal_id,
                period_id=period.id,
                statement_type=row["statement_type"],
                reported_label=row["label"],
                normalized_key=normalized_key,
                value=float(row["value"]),
                currency=(row["currency"] or deal.currency or "USD"),
                unit_scale=(row["unit_scale"] or deal.unit_scale),
                source_document_id=document_id,
                mapping_status="proposed" if normalized_key else "manual",
                confidence_score=confidence if normalized_key else None,
            )
            db.add(line_item)
            line_items_created += 1

    if document_id:
        doc = db.get(models.SourceDocument, document_id)
        if doc:
            doc.processing_status = "processed"

    db.commit()
    audit.record(
        db,
        entity_type="financial_import",
        entity_id=deal_id,
        action="import",
        actor_id=user.id,
        deal_id=deal_id,
        new_value={"periods_created": periods_created, "line_items_created": line_items_created},
    )
    db.commit()

    return schemas.ImportResult(
        document_id=document_id or uuid.uuid4(),
        periods_created=periods_created,
        line_items_created=line_items_created,
        unresolved_mappings=unresolved,
        warnings=warnings,
    )


@router.get("", response_model=list[schemas.FinancialPeriodOut])
def get_financials(deal_id: uuid.UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    require_deal_access(deal_id, db, user)
    periods = (
        db.query(models.FinancialPeriod)
        .filter_by(deal_id=deal_id)
        .order_by(models.FinancialPeriod.fiscal_year)
        .all()
    )
    return periods


@router.patch("/line-items/{line_item_id}", response_model=schemas.FinancialLineItemOut)
def update_line_item(
    deal_id: uuid.UUID,
    line_item_id: uuid.UUID,
    payload: schemas.FinancialLineItemUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    require_editor(deal_id, db, user)
    line_item = db.get(models.FinancialLineItem, line_item_id)
    if line_item is None or line_item.deal_id != deal_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Line item not found")

    old_value = schemas.FinancialLineItemOut.model_validate(line_item).model_dump(mode="json")
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(line_item, key, value)
    db.commit()
    db.refresh(line_item)
    audit.record(
        db,
        entity_type="financial_line_item",
        entity_id=line_item.id,
        action="update",
        actor_id=user.id,
        deal_id=deal_id,
        old_value=old_value,
        new_value=updates,
    )
    db.commit()
    return line_item


@router.post("/approve-mappings", response_model=list[schemas.FinancialLineItemOut])
def approve_mappings(
    deal_id: uuid.UUID,
    line_item_ids: list[uuid.UUID],
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """PRD 7.4: "Require user approval for material mappings before those
    values are designated as approved." """
    require_editor(deal_id, db, user)
    items = (
        db.query(models.FinancialLineItem)
        .filter(models.FinancialLineItem.deal_id == deal_id, models.FinancialLineItem.id.in_(line_item_ids))
        .all()
    )
    for item in items:
        if not item.normalized_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Line item {item.id} has no normalized_key; assign one before approving.",
            )
        item.mapping_status = "approved"
    db.commit()
    audit.record(
        db,
        entity_type="financial_line_item",
        entity_id=deal_id,
        action="approve_mappings",
        actor_id=user.id,
        deal_id=deal_id,
        new_value={"approved_ids": [str(i) for i in line_item_ids]},
    )
    db.commit()
    for item in items:
        db.refresh(item)
    return items


@router.get("/model-checks", response_model=schemas.ModelChecksReport)
def get_data_quality_checks(
    deal_id: uuid.UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)
):
    """PRD 7.4 required data-quality checks, run against currently approved
    historicals (separate from the full DCF model-check suite, which also
    needs a calculated scenario)."""
    require_deal_access(deal_id, db, user)
    result = build_historicals_for_deal(db, deal_id)
    checks = [
        check_no_missing_periods(result.historicals),
        check_currency_and_unit_consistency(result.currencies, result.unit_scales),
    ]
    for w in result.warnings:
        checks.append(
            schemas.ModelCheckOut(check_id="mapping_completeness", passed=False, message=w, severity="warning")
        )
    check_outs = [
        c if isinstance(c, schemas.ModelCheckOut) else schemas.ModelCheckOut(
            check_id=c.check_id, passed=c.passed, message=c.message, severity=c.severity
        )
        for c in checks
    ]
    has_blocking = any(not c.passed and c.severity == "error" for c in check_outs)
    return schemas.ModelChecksReport(checks=check_outs, has_blocking_failures=has_blocking)
