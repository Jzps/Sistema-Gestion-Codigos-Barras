from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Workspace(Base):
    """Tenant logico. Todos los datos (usuarios, productos, escaneos)
    pertenecen a exactamente un workspace."""

    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    users: Mapped[list["User"]] = relationship(back_populates="workspace")  # noqa: F821
    products: Mapped[list["Product"]] = relationship(back_populates="workspace")  # noqa: F821
    scans: Mapped[list["Scan"]] = relationship(back_populates="workspace")  # noqa: F821
