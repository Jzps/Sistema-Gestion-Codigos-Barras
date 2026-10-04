"""Logica de negocio de productos: correccion (PATCH) y eliminacion segura.

Politicas de dominio (ver docs/architecture.md):
- Editar un producto NO toca los scans: estos referencian product_id, y el
  historial muestra los datos actuales del producto via JOIN. Corregir un
  barcode o peso mal capturado se refleja en el historial, que es lo deseado.
- Un producto SOLO puede eliminarse si no tiene scans (409 en caso contrario).
  Para borrar uno con historial hay que eliminar antes los scans, uno a uno,
  de forma explicita. Asi se protege la integridad del historial.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.product import Product
from app.repositories import products as products_repo
from app.schemas.product import ProductUpdate
from app.services.errors import ConflictError, NotFoundError
from app.services.weight import to_kg

_DUPLICATE_BARCODE_MSG = "Ya existe un producto con ese código en este workspace"


def get_in_workspace(db: Session, workspace_id: int, product_id: int) -> Product:
    """Obtiene el producto validando que pertenece al workspace.
    Nunca confiar en un workspace_id enviado por el cliente."""
    product = products_repo.get_by_id_in_workspace(db, workspace_id, product_id)
    if product is None:
        raise NotFoundError("Producto no encontrado")
    return product


def update_product(
    db: Session, *, workspace_id: int, product_id: int, payload: ProductUpdate
) -> Product:
    product = get_in_workspace(db, workspace_id, product_id)
    # exclude_unset: solo se aplican los campos enviados por el cliente.
    fields = payload.model_dump(exclude_unset=True)

    new_barcode = fields.get("barcode_raw")
    if new_barcode is not None and new_barcode != product.barcode_raw:
        existing = products_repo.get_by_barcode(db, workspace_id, new_barcode)
        if existing is not None and existing.id != product.id:
            raise ConflictError(_DUPLICATE_BARCODE_MSG)
        product.barcode_raw = new_barcode

    for attr in ("barcode_type", "product_identifier", "product_name"):
        if attr in fields:
            setattr(product, attr, fields[attr])

    if "weight_value" in fields or "weight_unit" in fields:
        # null en peso = "sin cambio" (esas columnas no admiten null).
        new_value = (
            fields["weight_value"]
            if fields.get("weight_value") is not None
            else product.weight_value
        )
        new_unit = (
            fields["weight_unit"]
            if fields.get("weight_unit") is not None
            else product.weight_unit
        )
        product.weight_value = new_value
        product.weight_unit = new_unit
        product.weight_kg = to_kg(new_value, new_unit)

    try:
        db.commit()
    except IntegrityError:
        # Carrera improbable: otro usuario creo el mismo barcode justo ahora.
        db.rollback()
        raise ConflictError(_DUPLICATE_BARCODE_MSG) from None
    db.refresh(product)
    return product


def delete_product(db: Session, *, workspace_id: int, product_id: int) -> None:
    product = get_in_workspace(db, workspace_id, product_id)
    scan_count = products_repo.count_scans(db, product.id)
    if scan_count > 0:
        raise ConflictError(
            f"El producto tiene {scan_count} escaneo(s) registrados. "
            "Elimina primero los escaneos para no perder el historial."
        )
    products_repo.delete(db, product)
    db.commit()
