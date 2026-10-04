"""PATCH /api/products/{id}: correccion de productos."""

from decimal import Decimal

from tests.conftest import login, make_user


def _setup(client, db):
    make_user(db, username="op", password="secret123")
    login(client, "op", "secret123")


def _create_product(client, barcode="P-100", value="10", unit="KG", name=None):
    payload = {"barcode": barcode, "weight_value": value, "weight_unit": unit}
    if name:
        payload["product_name"] = name
    return client.post("/api/scans", json=payload).json()["product"]


def test_update_name_only_keeps_everything_else(client, db):
    _setup(client, db)
    product = _create_product(client, name="Nombre viejo")
    response = client.patch(
        f"/api/products/{product['id']}", json={"product_name": "Nombre nuevo"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["product_name"] == "Nombre nuevo"
    assert body["barcode_raw"] == "P-100"
    assert Decimal(str(body["weight_kg"])) == Decimal("10.000000")
    assert body["weight_unit"] == "KG"


def test_update_weight_kg_recalculates_weight_kg(client, db):
    _setup(client, db)
    product = _create_product(client)
    response = client.patch(
        f"/api/products/{product['id']}", json={"weight_value": "12.5"}
    )
    assert response.status_code == 200
    body = response.json()
    assert Decimal(str(body["weight_value"])) == Decimal("12.5")
    assert Decimal(str(body["weight_kg"])) == Decimal("12.500000")
    assert body["weight_unit"] == "KG"


def test_update_weight_lb_recalculates_weight_kg(client, db):
    _setup(client, db)
    product = _create_product(client)
    response = client.patch(
        f"/api/products/{product['id']}",
        json={"weight_value": "44.09", "weight_unit": "LB"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["weight_unit"] == "LB"
    assert Decimal(str(body["weight_kg"])).quantize(Decimal("0.01")) == Decimal("20.00")


def test_update_unit_only_recalculates_with_stored_value(client, db):
    _setup(client, db)
    product = _create_product(client, value="10", unit="KG")
    response = client.patch(
        f"/api/products/{product['id']}", json={"weight_unit": "LB"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["weight_unit"] == "LB"
    assert Decimal(str(body["weight_value"])) == Decimal("10")
    # 10 LB = 4.535924 kg (conversion existente, sin duplicar logica)
    assert Decimal(str(body["weight_kg"])) == Decimal("4.535924")


def test_update_barcode_keeps_history_linked_to_product(client, db):
    _setup(client, db)
    product = _create_product(client)
    client.post("/api/scans", json={"barcode": "P-100"})  # segundo escaneo

    response = client.patch(
        f"/api/products/{product['id']}", json={"barcode_raw": "P-100-CORREGIDO"}
    )
    assert response.status_code == 200
    assert response.json()["barcode_raw"] == "P-100-CORREGIDO"

    # Los scans NO se tocan: siguen apuntando al mismo product_id y el
    # historial refleja el dato corregido via JOIN.
    history = client.get("/api/scans").json()
    assert len(history) == 2
    assert all(row["product_id"] == product["id"] for row in history)
    assert all(row["barcode_raw"] == "P-100-CORREGIDO" for row in history)


def test_update_barcode_to_existing_returns_conflict(client, db):
    _setup(client, db)
    _create_product(client, barcode="P-200")
    other = _create_product(client, barcode="P-201")
    response = client.patch(
        f"/api/products/{other['id']}", json={"barcode_raw": "P-200"}
    )
    assert response.status_code == 409
    # El producto queda intacto
    assert client.get(f"/api/products/{other['id']}").json()["barcode_raw"] == "P-201"


def test_update_product_from_other_workspace_returns_404(client, db):
    _setup(client, db)
    product = _create_product(client)
    client.post("/api/auth/logout")

    make_user(db, workspace_name="WS B", username="userB", password="passB123")
    login(client, "userB", "passB123")
    response = client.patch(
        f"/api/products/{product['id']}", json={"product_name": "hackeado"}
    )
    assert response.status_code == 404
    # Sin revelar ni modificar nada en el otro workspace
    client.post("/api/auth/logout")
    login(client, "op", "secret123")
    assert client.get(f"/api/products/{product['id']}").json()["product_name"] is None


def test_update_requires_auth(client, db):
    _setup(client, db)
    product = _create_product(client)
    client.post("/api/auth/logout")
    response = client.patch(
        f"/api/products/{product['id']}", json={"product_name": "x"}
    )
    assert response.status_code == 401


def test_clear_optional_field_with_explicit_null(client, db):
    _setup(client, db)
    product = _create_product(client, name="Con nombre")
    response = client.patch(
        f"/api/products/{product['id']}", json={"product_name": None}
    )
    assert response.status_code == 200
    assert response.json()["product_name"] is None


def test_empty_patch_is_noop(client, db):
    _setup(client, db)
    product = _create_product(client, name="Sin cambios")
    response = client.patch(f"/api/products/{product['id']}", json={})
    assert response.status_code == 200
    assert response.json()["product_name"] == "Sin cambios"


def test_readonly_fields_are_ignored(client, db):
    _setup(client, db)
    product = _create_product(client)
    response = client.patch(
        f"/api/products/{product['id']}",
        json={"id": 999, "workspace_id": 999, "weight_kg": "999"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == product["id"]
    assert Decimal(str(body["weight_kg"])) == Decimal("10.000000")


def test_invalid_weight_value_rejected(client, db):
    _setup(client, db)
    product = _create_product(client)
    response = client.patch(
        f"/api/products/{product['id']}", json={"weight_value": "-5"}
    )
    assert response.status_code == 422


def test_invalid_weight_unit_rejected(client, db):
    _setup(client, db)
    product = _create_product(client)
    response = client.patch(
        f"/api/products/{product['id']}", json={"weight_unit": "OZ"}
    )
    assert response.status_code == 422
