"""Punto de entrada de la API SGCBP.

Arranque local (desde backend/):
    uvicorn app.main:app --reload
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import auth, health, products, reports, scans
from app.core.config import get_settings

logger = logging.getLogger("sgcbp")
settings = get_settings()

app = FastAPI(
    title="SGCBP API",
    version="1.0.0",
    description="Sistema de Gestión de Códigos de Barras y Pesos",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,  # necesario para la cookie HttpOnly
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(scans.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(reports.router, prefix="/api")


@app.exception_handler(Exception)
def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Nunca devolver stack traces al cliente."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
