from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.scan import Scan


def get_by_id_in_workspace(db: Session, workspace_id: int, scan_id: int) -> Scan | None:
    """Nunca resolver un scan por id sin validar el workspace."""
    return db.scalar(
        select(Scan).where(
            Scan.id == scan_id,
            Scan.workspace_id == workspace_id,
        )
    )


def create(db: Session, *, workspace_id: int, product_id: int, user_id: int) -> Scan:
    scan = Scan(workspace_id=workspace_id, product_id=product_id, user_id=user_id)
    db.add(scan)
    db.flush()  # el commit lo hace el servicio
    return scan


def delete(db: Session, scan: Scan) -> None:
    """Elimina SOLO el evento; el producto asociado queda intacto."""
    db.delete(scan)


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
