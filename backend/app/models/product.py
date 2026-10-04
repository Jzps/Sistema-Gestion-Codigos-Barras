from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Product(Base):
    """Producto identificado por su codigo de barras dentro de un workspace.

    Regla de identidad V1: la unicidad es (workspace_id, barcode_raw).
    El codigo se conserva integro en barcode_raw; barcode_type y
    product_identifier quedan preparados para el futuro parser GS1 (Fase 4).
    """

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "barcode_raw", name="uq_products_workspace_barcode"
        ),
        CheckConstraint("weight_unit IN ('KG', 'LB')", name="ck_products_weight_unit"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    barcode_raw: Mapped[str] = mapped_column(String(128), nullable=False)
    barcode_type: Mapped[str | None] = mapped_column(String(32))
    product_identifier: Mapped[str | None] = mapped_column(String(64))
    product_name: Mapped[str | None] = mapped_column(String(255))

    # Peso tal como lo introdujo el usuario + normalizacion a kg.
    weight_value: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    weight_unit: Mapped[str] = mapped_column(String(2), nullable=False)  # "KG" | "LB"
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    workspace: Mapped["Workspace"] = relationship(back_populates="products")  # noqa: F821
    scans: Mapped[list["Scan"]] = relationship(back_populates="product")  # noqa: F821
