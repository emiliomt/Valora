import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.db import get_db
from app.deps import get_current_user, require_deal_access, require_editor, require_workspace_role
from app.services import audit

router = APIRouter(prefix="/api/deals", tags=["deals"])


def _to_out(deal: models.Deal) -> schemas.DealOut:
    out = schemas.DealOut.model_validate(deal)
    out.ready_for_valuation = deal.is_ready_for_valuation()
    return out


@router.post("", response_model=schemas.DealOut, status_code=status.HTTP_201_CREATED)
def create_deal(
    payload: schemas.DealCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    require_workspace_role(payload.workspace_id, db, user, allowed_roles=("admin", "editor"))
    deal = models.Deal(**payload.model_dump(), status="draft", created_by=user.id)
    db.add(deal)
    db.commit()
    db.refresh(deal)
    audit.record(
        db,
        entity_type="deal",
        entity_id=deal.id,
        action="create",
        actor_id=user.id,
        workspace_id=deal.workspace_id,
        deal_id=deal.id,
        new_value=payload.model_dump(mode="json"),
    )
    db.commit()
    return _to_out(deal)


@router.get("", response_model=list[schemas.DealOut])
def list_deals(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    require_workspace_role(workspace_id, db, user)
    deals = db.query(models.Deal).filter_by(workspace_id=workspace_id).all()
    return [_to_out(d) for d in deals]


@router.get("/{deal_id}", response_model=schemas.DealOut)
def get_deal(deal_id: uuid.UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    deal = require_deal_access(deal_id, db, user)
    return _to_out(deal)


@router.patch("/{deal_id}", response_model=schemas.DealOut)
def update_deal(
    deal_id: uuid.UUID,
    payload: schemas.DealUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    deal = require_editor(deal_id, db, user)
    old_value = schemas.DealOut.model_validate(deal).model_dump(mode="json")
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(deal, key, value)
    db.commit()
    db.refresh(deal)
    audit.record(
        db,
        entity_type="deal",
        entity_id=deal.id,
        action="update",
        actor_id=user.id,
        workspace_id=deal.workspace_id,
        deal_id=deal.id,
        old_value=old_value,
        new_value=updates,
    )
    db.commit()
    return _to_out(deal)


@router.delete("/{deal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deal(deal_id: uuid.UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    deal = require_deal_access(deal_id, db, user, allowed_roles=("admin",))
    db.delete(deal)
    db.commit()
    return None
