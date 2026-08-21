from sqlalchemy.orm import Session

from app import models

DEFAULT_WORKSPACE_NAME = "Personal"


def next_default_workspace_name(db: Session, user: models.User) -> str:
    """Pick Personal, then Workspace 2, 3, … so a nameless '+ Workspace' click still works."""
    existing = (
        db.query(models.Workspace.name)
        .join(models.WorkspaceMembership)
        .filter(models.WorkspaceMembership.user_id == user.id)
        .all()
    )
    names = {row[0] for row in existing}
    if DEFAULT_WORKSPACE_NAME not in names:
        return DEFAULT_WORKSPACE_NAME
    index = 2
    while f"Workspace {index}" in names:
        index += 1
    return f"Workspace {index}"


def provision_workspace(
    db: Session, user: models.User, name: str = DEFAULT_WORKSPACE_NAME
) -> models.Workspace:
    """Create a workspace and make `user` its admin. Caller owns the transaction."""
    workspace = models.Workspace(name=name)
    db.add(workspace)
    db.flush()
    membership = models.WorkspaceMembership(workspace_id=workspace.id, user_id=user.id, role="admin")
    db.add(membership)
    return workspace
