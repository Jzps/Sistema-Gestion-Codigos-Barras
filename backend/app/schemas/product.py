from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


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
