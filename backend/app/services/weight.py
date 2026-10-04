"""Conversion de pesos. Unica fuente de verdad para KG/LB.

1 LB = 0.45359237 KG
1 KG = 2.2046226218 LB

Se usa Decimal en todo el calculo para evitar errores binarios de float.
El peso persistido se normaliza siempre en kilogramos (weight_kg).
"""

from decimal import Decimal, ROUND_HALF_UP

KG_PER_LB = Decimal("0.45359237")
LB_PER_KG = Decimal("2.2046226218")

VALID_UNITS = ("KG", "LB")

_KG_QUANT = Decimal("0.000001")


def to_kg(value: Decimal, unit: str) -> Decimal:
    """Normaliza cualquier peso soportado a kilogramos (6 decimales)."""
    if unit not in VALID_UNITS:
        raise ValueError(f"Unsupported weight unit: {unit!r}")
    kg = value if unit == "KG" else value * KG_PER_LB
    return kg.quantize(_KG_QUANT, rounding=ROUND_HALF_UP)


def to_lb(weight_kg: Decimal) -> Decimal:
    """Equivalente en libras de un peso ya normalizado en kg."""
    return (weight_kg * LB_PER_KG).quantize(_KG_QUANT, rounding=ROUND_HALF_UP)
