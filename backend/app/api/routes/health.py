from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.api.deps import DbSession

router = APIRouter(tags=["health"])


@router.get("/health", summary="Estado de la API y la base de datos")
def health(db: DbSession) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from None
    return {"status": "ok", "db": "ok"}
