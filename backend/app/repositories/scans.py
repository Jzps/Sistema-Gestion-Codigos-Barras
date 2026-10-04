from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.scan import Scan


def create(db: Session, *, workspace_id: int, product_id: int, user_id: int) -> Scan:
    scan = Scan(workspace_id=workspace_id, product_id=product_id, user_id=user_id)
    db.add(scan)
    db.flush()  # el commit lo hace el servicio
    return scan


def list_history(
    db: Session, workspace_id: int, *, limit: int = 100, offset: int = 0
) -> list[Scan]:
    """Historial del workspace, mas reciente primero, con producto y usuario."""
    return list(
        db.scalars(
            select(Scan)
            .options(joinedload(Scan.product), joinedload(Scan.user))
            .where(Scan.workspace_id == workspace_id)
            .order_by(Scan.scanned_at.desc(), Scan.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
