"""Audit logging (PRD 7.1: "Every material write action records user,
timestamp, prior value, and new value.")"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app import models


def record(
    db: Session,
    *,
    entity_type: str,
    entity_id: uuid.UUID | str,
    action: str,
    actor_id: uuid.UUID | None,
    workspace_id: uuid.UUID | None = None,
    deal_id: uuid.UUID | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
) -> models.AuditLog:
    entry = models.AuditLog(
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        actor_id=actor_id,
        workspace_id=workspace_id,
        deal_id=deal_id,
        old_value_json=old_value,
        new_value_json=new_value,
    )
    db.add(entry)
    return entry
