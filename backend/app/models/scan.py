from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Scan(Base):
    """Evento de escaneo. Cada lectura de un codigo (nuevo o existente)
    genera exactamente un registro. Es el historial auditable del workspace."""

    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    workspace: Mapped["Workspace"] = relationship(back_populates="scans")  # noqa: F821
    product: Mapped["Product"] = relationship(back_populates="scans")  # noqa: F821
    user: Mapped["User"] = relationship(back_populates="scans")  # noqa: F821
