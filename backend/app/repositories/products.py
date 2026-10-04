from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.scan import Scan


def get_by_barcode(db: Session, workspace_id: int, barcode_raw: str) -> Product | None:
    """Busqueda principal de V1: workspace + barcode_raw."""
    return db.scalar(
        select(Product).where(
            Product.workspace_id == workspace_id,
            Product.barcode_raw == barcode_raw,
        )
    )


def get_by_id_in_workspace(
    db: Session, workspace_id: int, product_id: int
) -> Product | None:
    """Nunca resolver un producto por id sin validar el workspace."""
    return db.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.workspace_id == workspace_id,
        )
    )


def list_by_workspace(db: Session, workspace_id: int, limit: int = 500) -> list[Product]:
    return list(
        db.scalars(
            select(Product)
            .where(Product.workspace_id == workspace_id)
            .order_by(Product.created_at.desc(), Product.id.desc())
            .limit(limit)
        )
    )


def create(
    db: Session,
    *,
    workspace_id: int,
    barcode_raw: str,
    weight_value: Decimal,
    weight_unit: str,
    weight_kg: Decimal,
    product_name: str | None = None,
    barcode_type: str | None = None,
    product_identifier: str | None = None,
) -> Product:
    product = Product(
        workspace_id=workspace_id,
        barcode_raw=barcode_raw,
        barcode_type=barcode_type,
        product_identifier=product_identifier,
        product_name=product_name,
        weight_value=weight_value,
        weight_unit=weight_unit,
        weight_kg=weight_kg,
    )
    db.add(product)
    db.flush()  # obtiene id dentro de la transaccion; el commit lo hace el servicio
    return product


def count_scans(db: Session, product_id: int) -> int:
    """Numero de escaneos asociados al producto (politica de borrado)."""
    return (
        db.scalar(select(func.count(Scan.id)).where(Scan.product_id == product_id))
        or 0
    )


def delete(db: Session, product: Product) -> None:
    """El commit lo hace el servicio. NUNCA llamar con scans asociados:
    la FK tiene ON DELETE CASCADE a nivel de BD y borraria el historial;
    la politica la impone product_service."""
    db.delete(product)
