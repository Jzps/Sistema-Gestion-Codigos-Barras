"""Modelos ORM. Importar este paquete registra todos los modelos en Base.metadata
(necesario para Alembic)."""

from app.models.product import Product
from app.models.scan import Scan
from app.models.user import User
from app.models.workspace import Workspace

__all__ = ["Workspace", "User", "Product", "Scan"]
