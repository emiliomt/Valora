from sqlalchemy.orm import Session

from app import models

DEFAULT_WORKSPACE_NAME = "Personal"


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
