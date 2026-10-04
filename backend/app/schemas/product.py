from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    barcode_raw: str
    barcode_type: str | None
    product_identifier: str | None
    product_name: str | None
    weight_value: Decimal
    weight_unit: str
    weight_kg: Decimal
    created_at: datetime


class ProductUpdate(BaseModel):
    """Actualizacion parcial de un producto (PATCH).

    Semantica:
    - Campo ausente -> no se modifica.
    - null explicito en campos opcionales (product_name, barcode_type,
      product_identifier) -> limpia el campo.
    - weight_value / weight_unit -> si llega alguno, se recalcula weight_kg
      combinando con el valor almacenado del otro (ver product_service).

    Nunca editables: id, workspace_id, created_at, updated_at y weight_kg
    (derivado del peso; lo calcula el backend).
    """

    barcode_raw: str | None = Field(default=None, min_length=1, max_length=128)
    barcode_type: str | None = Field(default=None, max_length=32)
    product_identifier: str | None = Field(default=None, max_length=64)
    product_name: str | None = Field(default=None, max_length=255)
    weight_value: Decimal | None = Field(
        default=None, gt=0, le=Decimal("99999999.9999")
    )
    weight_unit: Literal["KG", "LB"] | None = None

    @field_validator("barcode_raw")
    @classmethod
    def barcode_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("barcode must not be blank")
        return value

    @field_validator("barcode_type", "product_identifier", "product_name")
    @classmethod
    def strip_or_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None
