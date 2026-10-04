from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.product import ProductOut

WeightUnit = Literal["KG", "LB"]


class ScanRequest(BaseModel):
    """Entrada unica del flujo de escaneo.

    - Solo barcode: si el producto existe se registra el escaneo; si no,
      el backend responde status="needs_weight".
    - barcode + peso + unidad: crea el producto (si no existe) y registra
      el escaneo. Si el producto ya existe, el peso enviado se IGNORA y se
      reutiliza el almacenado (el backend es la autoridad).
    """

    barcode: str = Field(min_length=1, max_length=128)
    weight_value: Decimal | None = Field(default=None, gt=0, le=Decimal("99999999.9999"))
    weight_unit: WeightUnit | None = None
    product_name: str | None = Field(default=None, max_length=255)

    @field_validator("barcode")
    @classmethod
    def barcode_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("barcode must not be blank")
        return value

    @field_validator("product_name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def weight_fields_together(self) -> "ScanRequest":
        if (self.weight_value is None) != (self.weight_unit is None):
            raise ValueError("weight_value and weight_unit must be provided together")
        return self


class ScanOut(BaseModel):
    """Fila del historial de escaneos (producto y usuario desnormalizados)."""

    id: int
    scanned_at: datetime
    product_id: int
    user_id: int
    username: str
    barcode_raw: str
    product_name: str | None
    weight_value: Decimal
    weight_unit: str
    weight_kg: Decimal
    weight_lb: Decimal


class ScanResponse(BaseModel):
    """Resultado de POST /api/scans.

    status:
    - "existing": el codigo ya existia; se reutilizo el peso almacenado.
    - "created": producto nuevo creado con el peso enviado.
    - "needs_weight": codigo nuevo; el frontend debe pedir peso y unidad.
    """

    status: Literal["existing", "created", "needs_weight"]
    barcode: str
    product: ProductOut | None = None
    scan: ScanOut | None = None
