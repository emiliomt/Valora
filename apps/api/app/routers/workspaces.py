from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.db import get_db
from app.deps import get_current_user
from app.services.workspaces import next_default_workspace_name, provision_workspace

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.post("", response_model=schemas.WorkspaceOut, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: schemas.WorkspaceCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = provision_workspace(db, user, payload.name or next_default_workspace_name(db, user))
    db.commit()
    db.refresh(workspace)
    return workspace


@router.get("", response_model=list[schemas.WorkspaceOut])
def list_workspaces(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return (
        db.query(models.Workspace)
        .join(models.WorkspaceMembership)
        .filter(models.WorkspaceMembership.user_id == user.id)
        .all()
    )
