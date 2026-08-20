import uuid
from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_exception
    user = db.get(models.User, user_id)
    if user is None:
        raise credentials_exception
    return user


def require_workspace_role(
    workspace_id: uuid.UUID,
    db: Session,
    user: models.User,
    allowed_roles: tuple[str, ...] = ("admin", "editor", "viewer"),
) -> models.WorkspaceMembership:
    """Enforce workspace-level authorization (PRD 7.1 acceptance criteria)."""
    membership = (
        db.query(models.WorkspaceMembership)
        .filter_by(workspace_id=workspace_id, user_id=user.id)
        .first()
    )
    if membership is None or membership.role not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this workspace")
    return membership


def require_deal_access(
    deal_id: uuid.UUID,
    db: Session,
    user: models.User,
    allowed_roles: tuple[str, ...] = ("admin", "editor", "viewer"),
) -> models.Deal:
    deal = db.get(models.Deal, deal_id)
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    require_workspace_role(deal.workspace_id, db, user, allowed_roles)
    return deal


def require_editor(
    deal_id: uuid.UUID,
    db: Session,
    user: models.User,
) -> models.Deal:
    return require_deal_access(deal_id, db, user, allowed_roles=("admin", "editor"))
