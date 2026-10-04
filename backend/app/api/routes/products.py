from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.repositories import products as products_repo
from app.schemas.product import ProductOut, ProductUpdate
from app.services import product_service

router = APIRouter(prefix="/products", tags=["products"])

_NOT_FOUND = {"description": "Producto inexistente o perteneciente a otro workspace"}


@router.get(
    "",
    response_model=list[ProductOut],
    summary="Lista los productos del workspace",
)
def list_products(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=500, ge=1, le=1000),
) -> list[ProductOut]:
    products = products_repo.list_by_workspace(db, user.workspace_id, limit=limit)
    return [ProductOut.model_validate(product) for product in products]


@router.get(
    "/{product_id}",
    response_model=ProductOut,
    summary="Obtiene un producto por id",
    responses={404: _NOT_FOUND},
)
def get_product(product_id: int, user: CurrentUser, db: DbSession) -> ProductOut:
    # Se busca por (id + workspace): un id de otro workspace devuelve 404,
    # sin revelar que el recurso existe.
    product = product_service.get_in_workspace(db, user.workspace_id, product_id)
    return ProductOut.model_validate(product)


@router.patch(
    "/{product_id}",
    response_model=ProductOut,
    summary="Corrige campos editables de un producto (actualización parcial)",
    responses={
        404: _NOT_FOUND,
        409: {"description": "El código de barras ya existe en este workspace"},
    },
)
def update_product(
    product_id: int, payload: ProductUpdate, user: CurrentUser, db: DbSession
) -> ProductOut:
    """Edita barcode, nombre, identificadores y/o peso. Recalcula weight_kg
    cuando cambia el peso o la unidad. No modifica los scans existentes."""
    product = product_service.update_product(
        db, workspace_id=user.workspace_id, product_id=product_id, payload=payload
    )
    return ProductOut.model_validate(product)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina un producto (solo si no tiene escaneos)",
    responses={
        404: _NOT_FOUND,
        409: {
            "description": "El producto tiene escaneos; deben eliminarse primero"
        },
    },
)
def delete_product(product_id: int, user: CurrentUser, db: DbSession) -> None:
    """Política de borrado segura: un producto con historial no se puede
    eliminar hasta que sus escaneos se eliminen explícitamente uno a uno."""
    product_service.delete_product(
        db, workspace_id=user.workspace_id, product_id=product_id
    )
