"""Aislamiento logico entre workspaces (requisito critico).

Mismo barcode en dos workspaces: dos productos distintos con pesos
distintos, y ningun usuario ve nada del otro workspace.
"""

from decimal import Decimal

from tests.conftest import login, make_user


def _seed_two_workspaces(client, db):
    make_user(db, workspace_name="WS A", username="userA", password="passA123")
    make_user(db, workspace_name="WS B", username="userB", password="passB123")

    login(client, "userA", "passA123")
    product_a = client.post(
        "/api/scans",
        json={"barcode": "123", "weight_value": "10", "weight_unit": "KG"},
    ).json()["product"]
    client.post("/api/auth/logout")

    login(client, "userB", "passB123")
    product_b = client.post(
        "/api/scans",
        json={"barcode": "123", "weight_value": "20", "weight_unit": "KG"},
    ).json()["product"]
    client.post("/api/auth/logout")
    return product_a, product_b


def test_same_barcode_different_workspaces_are_independent(client, db):
    product_a, product_b = _seed_two_workspaces(client, db)
    assert product_a["id"] != product_b["id"]
    assert Decimal(str(product_a["weight_kg"])) == Decimal("10.000000")
    assert Decimal(str(product_b["weight_kg"])) == Decimal("20.000000")


def test_scan_resolves_product_within_own_workspace(client, db):
    _seed_two_workspaces(client, db)
    login(client, "userA", "passA123")
    body = client.post("/api/scans", json={"barcode": "123"}).json()
    assert body["status"] == "existing"
    assert Decimal(str(body["product"]["weight_kg"])) == Decimal("10.000000")


def test_user_cannot_read_product_from_other_workspace(client, db):
    _seed_two_workspaces(client, db)
    product_b_id = None
    login(client, "userB", "passB123")
    product_b_id = client.get("/api/products").json()[0]["id"]
    client.post("/api/auth/logout")

    login(client, "userA", "passA123")
    response = client.get(f"/api/products/{product_b_id}")
    assert response.status_code == 404  # no revelar que existe en otro workspace


def test_history_only_contains_own_workspace(client, db):
    _seed_two_workspaces(client, db)
    login(client, "userA", "passA123")
    history = client.get("/api/scans").json()
    assert len(history) == 1
    assert history[0]["username"] == "userA"
    assert Decimal(str(history[0]["weight_kg"])) == Decimal("10.000000")


def test_product_list_only_contains_own_workspace(client, db):
    _seed_two_workspaces(client, db)
    login(client, "userB", "passB123")
    products = client.get("/api/products").json()
    assert len(products) == 1
    assert Decimal(str(products[0]["weight_kg"])) == Decimal("20.000000")
