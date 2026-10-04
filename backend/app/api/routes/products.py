from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.repositories import products as products_repo
from app.schemas.product import ProductOut

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=500, ge=1, le=1000),
) -> list[ProductOut]:
    products = products_repo.list_by_workspace(db, user.workspace_id, limit=limit)
    return [ProductOut.model_validate(product) for product in products]


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, user: CurrentUser, db: DbSession) -> ProductOut:
    # Se busca por (id + workspace): un id de otro workspace devuelve 404,
    # sin revelar que el recurso existe.
    product = products_repo.get_by_id_in_workspace(db, user.workspace_id, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado"
        )
    return ProductOut.model_validate(product)
