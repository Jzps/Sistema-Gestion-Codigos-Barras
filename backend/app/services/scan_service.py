"""Logica del flujo de escaneo (corazon del MVP).

ESCANEAR -> ¿existe (workspace, barcode_raw)?
  NO  -> sin peso: status "needs_weight" (el frontend pedira peso/unidad)
         con peso: normalizar a kg, crear producto, registrar scan -> "created"
  SI  -> reutilizar peso almacenado, registrar scan -> "existing"

Cada escaneo procesado genera exactamente un registro en SCANS.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.scan import Scan
from app.repositories import products as products_repo
from app.repositories import scans as scans_repo
from app.schemas.product import ProductOut
from app.schemas.scan import ScanOut, ScanRequest, ScanResponse
from app.services.weight import to_kg, to_lb


def to_scan_out(scan: Scan) -> ScanOut:
    """Convierte un Scan ORM (con product y user cargados) en fila de historial."""
    product = scan.product
    return ScanOut(
        id=scan.id,
        scanned_at=scan.scanned_at,
        product_id=product.id,
        user_id=scan.user_id,
        username=scan.user.username,
        barcode_raw=product.barcode_raw,
        product_name=product.product_name,
        weight_value=product.weight_value,
        weight_unit=product.weight_unit,
        weight_kg=product.weight_kg,
        weight_lb=to_lb(product.weight_kg),
    )


def handle_scan(
    db: Session, *, workspace_id: int, user_id: int, payload: ScanRequest
) -> ScanResponse:
    barcode = payload.barcode
    product = products_repo.get_by_barcode(db, workspace_id, barcode)

    if product is None:
        if payload.weight_value is None:
            # Producto nuevo y sin datos de peso: el frontend debe solicitarlos.
            return ScanResponse(status="needs_weight", barcode=barcode)
        product = products_repo.create(
            db,
            workspace_id=workspace_id,
            barcode_raw=barcode,
            product_name=payload.product_name,
            weight_value=payload.weight_value,
            weight_unit=payload.weight_unit,  # validado por Pydantic: "KG" | "LB"
            weight_kg=to_kg(payload.weight_value, payload.weight_unit),
        )
        status = "created"
    else:
        # El producto ya existe: se ignora cualquier peso enviado y se
        # reutiliza el almacenado (no se vuelve a pedir el peso).
        status = "existing"

    scan = scans_repo.create(
        db, workspace_id=workspace_id, product_id=product.id, user_id=user_id
    )
    try:
        db.commit()
    except IntegrityError:
        # Cara a cara poco probable: otro usuario creo el mismo
        # (workspace, barcode) al mismo tiempo. Se reutiliza ese producto.
        db.rollback()
        product = products_repo.get_by_barcode(db, workspace_id, barcode)
        if product is None:
            raise
        scan = scans_repo.create(
            db, workspace_id=workspace_id, product_id=product.id, user_id=user_id
        )
        db.commit()
        status = "existing"

    db.refresh(scan)
    return ScanResponse(
        status=status,
        barcode=barcode,
        product=ProductOut.model_validate(product),
        scan=to_scan_out(scan),
    )
