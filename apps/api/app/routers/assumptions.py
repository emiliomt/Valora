import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.db import get_db
from app.deps import get_current_user, require_deal_access, require_editor
from app.services import audit

router = APIRouter(prefix="/api/deals/{deal_id}/assumptions", tags=["assumptions"])

VALID_SCENARIOS = {"base", "bull", "bear"}


@router.get("", response_model=list[schemas.AssumptionSetOut])
def list_assumption_sets(
    deal_id: uuid.UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)
):
    require_deal_access(deal_id, db, user)
    return db.query(models.AssumptionSet).filter_by(deal_id=deal_id).all()


@router.put("/{scenario}", response_model=schemas.AssumptionSetOut)
def upsert_assumption_set(
    deal_id: uuid.UUID,
    scenario: str,
    payload: schemas.AssumptionSetUpsert,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Full-replace upsert of one scenario's assumption set (PRD 7.6:
    "Every change recalculates dependent schedules and outputs" — the
    recalculation itself happens on-demand via the model-versions calculate
    endpoint, not here, so edits stay cheap and don't require a valuation
    to already exist)."""
    if scenario not in VALID_SCENARIOS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"scenario must be one of {VALID_SCENARIOS}")
    if payload.wacc <= payload.terminal_growth_rate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Terminal growth rate must be less than WACC (PRD 7.6 acceptance criteria).",
        )
    require_editor(deal_id, db, user)

    assumption_set = db.query(models.AssumptionSet).filter_by(deal_id=deal_id, scenario=scenario).first()
    old_value = None
    if assumption_set is None:
        assumption_set = models.AssumptionSet(deal_id=deal_id, scenario=scenario)
        db.add(assumption_set)
        db.flush()
    else:
        old_value = schemas.AssumptionSetOut.model_validate(assumption_set).model_dump(mode="json")
        db.query(models.Assumption).filter_by(assumption_set_id=assumption_set.id).delete()

    assumption_set.name = payload.name or f"{scenario.capitalize()} case"
    assumption_set.wacc = payload.wacc
    assumption_set.terminal_growth_rate = payload.terminal_growth_rate
    assumption_set.status = "draft"

    for a in payload.assumptions:
        db.add(
            models.Assumption(
                assumption_set_id=assumption_set.id,
                key=a.key,
                label=a.label,
                fiscal_year=a.fiscal_year,
                value=a.value,
                unit=a.unit,
                origin=a.origin,
                rationale=a.rationale,
                is_locked=a.is_locked,
            )
        )

    db.commit()
    db.refresh(assumption_set)
    audit.record(
        db,
        entity_type="assumption_set",
        entity_id=assumption_set.id,
        action="upsert",
        actor_id=user.id,
        deal_id=deal_id,
        old_value=old_value,
        new_value=schemas.AssumptionSetOut.model_validate(assumption_set).model_dump(mode="json"),
    )
    db.commit()
    return assumption_set


@router.post("/{scenario}/clone-to/{target_scenario}", response_model=schemas.AssumptionSetOut)
def clone_scenario(
    deal_id: uuid.UUID,
    scenario: str,
    target_scenario: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if scenario not in VALID_SCENARIOS or target_scenario not in VALID_SCENARIOS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"scenario must be one of {VALID_SCENARIOS}")
    require_editor(deal_id, db, user)

    source = db.query(models.AssumptionSet).filter_by(deal_id=deal_id, scenario=scenario).first()
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No assumption set for scenario '{scenario}'")

    target = db.query(models.AssumptionSet).filter_by(deal_id=deal_id, scenario=target_scenario).first()
    if target is None:
        target = models.AssumptionSet(deal_id=deal_id, scenario=target_scenario)
        db.add(target)
        db.flush()
    else:
        db.query(models.Assumption).filter_by(assumption_set_id=target.id).delete()

    target.name = f"{target_scenario.capitalize()} case"
    target.wacc = source.wacc
    target.terminal_growth_rate = source.terminal_growth_rate
    target.status = "draft"
    for a in source.assumptions:
        db.add(
            models.Assumption(
                assumption_set_id=target.id,
                key=a.key,
                label=a.label,
                fiscal_year=a.fiscal_year,
                value=a.value,
                unit=a.unit,
                origin=a.origin,
                rationale=a.rationale,
                is_locked=False,
            )
        )
    db.commit()
    db.refresh(target)
    return target
