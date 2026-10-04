"""Flujo de escaneo: el corazon del MVP."""

from decimal import Decimal

from tests.conftest import login, make_user


def _setup(client, db):
    make_user(db, username="op", password="secret123")
    login(client, "op", "secret123")


def test_new_barcode_without_weight_asks_for_weight(client, db):
    _setup(client, db)
    response = client.post("/api/scans", json={"barcode": "7500000000001"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_weight"
    assert body["barcode"] == "7500000000001"
    # No se registra nada todavia.
    assert client.get("/api/scans").json() == []


def test_new_barcode_with_weight_creates_product_and_scan(client, db):
    _setup(client, db)
    response = client.post(
        "/api/scans",
        json={
            "barcode": "7500000000002",
            "weight_value": "44.09",
            "weight_unit": "LB",
            "product_name": "Caja prueba",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "created"
    product = body["product"]
    assert product["barcode_raw"] == "7500000000002"
    assert product["weight_unit"] == "LB"
    assert Decimal(str(product["weight_value"])) == Decimal("44.09")
    # Conversion LB -> KG persistida normalizada
    assert abs(Decimal(str(product["weight_kg"])) - Decimal("20")) < Decimal("0.01")
    assert body["scan"]["username"] == "op"


def test_second_scan_reuses_stored_weight(client, db):
    _setup(client, db)
    created = client.post(
        "/api/scans",
        json={"barcode": "7500000000003", "weight_value": "10", "weight_unit": "KG"},
    ).json()
    again = client.post("/api/scans", json={"barcode": "7500000000003"})
    assert again.status_code == 201
    body = again.json()
    assert body["status"] == "existing"
    assert body["product"]["id"] == created["product"]["id"]
    assert Decimal(str(body["product"]["weight_kg"])) == Decimal("10.000000")

    history = client.get("/api/scans").json()
    assert len(history) == 2  # cada escaneo crea un evento
    assert all(row["username"] == "op" for row in history)
    assert all(row["barcode_raw"] == "7500000000003" for row in history)


def test_weight_sent_for_existing_product_is_ignored(client, db):
    _setup(client, db)
    client.post(
        "/api/scans",
        json={"barcode": "7500000000004", "weight_value": "10", "weight_unit": "KG"},
    )
    response = client.post(
        "/api/scans",
        json={"barcode": "7500000000004", "weight_value": "99", "weight_unit": "KG"},
    )
    body = response.json()
    assert body["status"] == "existing"
    assert Decimal(str(body["product"]["weight_kg"])) == Decimal("10.000000")


def test_weight_value_without_unit_is_invalid(client, db):
    _setup(client, db)
    response = client.post(
        "/api/scans", json={"barcode": "7500000000005", "weight_value": "10"}
    )
    assert response.status_code == 422


def test_blank_barcode_is_invalid(client, db):
    _setup(client, db)
    assert client.post("/api/scans", json={"barcode": "   "}).status_code == 422
    assert client.post("/api/scans", json={"barcode": ""}).status_code == 422


def test_history_is_ordered_newest_first(client, db):
    _setup(client, db)
    for i in range(3):
        client.post(
            "/api/scans",
            json={
                "barcode": f"CODE-{i}",
                "weight_value": "1",
                "weight_unit": "KG",
            },
        )
    history = client.get("/api/scans").json()
    ids = [row["id"] for row in history]
    assert ids == sorted(ids, reverse=True)
