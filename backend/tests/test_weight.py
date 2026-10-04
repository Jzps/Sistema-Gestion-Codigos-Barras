"""Conversion KG/LB: la regla numerica central del dominio."""

from decimal import Decimal

import pytest

from app.services.weight import to_kg, to_lb


def test_lb_to_kg_known_value():
    # Caso del enunciado: 44.09 LB ≈ 20.00 KG
    kg = to_kg(Decimal("44.09"), "LB")
    assert kg.quantize(Decimal("0.01")) == Decimal("20.00")


def test_kg_passes_through_normalized():
    assert to_kg(Decimal("10"), "KG") == Decimal("10.000000")


def test_kg_to_lb():
    assert to_lb(Decimal("20.000000")).quantize(Decimal("0.01")) == Decimal("44.09")


def test_round_trip_lb_kg_lb():
    kg = to_kg(Decimal("44.09"), "LB")
    assert abs(to_lb(kg) - Decimal("44.09")) < Decimal("0.01")


def test_invalid_unit_rejected():
    with pytest.raises(ValueError):
        to_kg(Decimal("1"), "OZ")
