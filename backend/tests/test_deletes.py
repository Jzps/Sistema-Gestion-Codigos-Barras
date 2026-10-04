"""DELETE /api/products/{id} y DELETE /api/scans/{id}: borrado seguro."""

from tests.conftest import login, make_user


def _setup(client, db):
    make_user(db, username="op", password="secret123")
    login(client, "op", "secret123")


def _create_product_with_scans(client, barcode="DEL-1", scans=1):
    product = client.post(
        "/api/scans",
        json={"barcode": barcode, "weight_value": "10", "weight_unit": "KG"},
    ).json()["product"]
    for _ in range(scans - 1):
        client.post("/api/scans", json={"barcode": barcode})
    return product


# ------------------------- DELETE producto ----------------------------------


def test_delete_product_with_scans_returns_409_and_keeps_everything(client, db):
    _setup(client, db)
    product = _create_product_with_scans(client, scans=2)
    response = client.delete(f"/api/products/{product['id']}")
    assert response.status_code == 409
    # Nada se borra: ni el producto ni su historial
    assert client.get(f"/api/products/{product['id']}").status_code == 200
    assert len(client.get("/api/scans").json()) == 2


def test_delete_product_after_deleting_its_scans(client, db):
    _setup(client, db)
    product = _create_product_with_scans(client, scans=1)
    scan_id = client.get("/api/scans").json()[0]["id"]

    assert client.delete(f"/api/scans/{scan_id}").status_code == 204
    response = client.delete(f"/api/products/{product['id']}")
    assert response.status_code == 204
    assert client.get(f"/api/products/{product['id']}").status_code == 404


def test_delete_product_from_other_workspace_returns_404(client, db):
    _setup(client, db)
    product = _create_product_with_scans(client)
    client.post("/api/auth/logout")

    make_user(db, workspace_name="WS B", username="userB", password="passB123")
    login(client, "userB", "passB123")
    assert client.delete(f"/api/products/{product['id']}").status_code == 404


def test_delete_product_requires_auth(client, db):
    _setup(client, db)
    product = _create_product_with_scans(client)
    client.post("/api/auth/logout")
    assert client.delete(f"/api/products/{product['id']}").status_code == 401


# ------------------------- DELETE scan --------------------------------------


def test_delete_scan_removes_history_entry_but_keeps_product(client, db):
    _setup(client, db)
    product = _create_product_with_scans(client, scans=2)
    history = client.get("/api/scans").json()
    assert len(history) == 2

    response = client.delete(f"/api/scans/{history[0]['id']}")
    assert response.status_code == 204

    remaining = client.get("/api/scans").json()
    assert len(remaining) == 1  # historial actualizado
    assert remaining[0]["id"] == history[1]["id"]
    # El producto NO se elimina con el scan
    assert client.get(f"/api/products/{product['id']}").status_code == 200


def test_delete_scan_twice_returns_404(client, db):
    _setup(client, db)
    _create_product_with_scans(client, scans=1)
    scan_id = client.get("/api/scans").json()[0]["id"]
    assert client.delete(f"/api/scans/{scan_id}").status_code == 204
    assert client.delete(f"/api/scans/{scan_id}").status_code == 404


def test_delete_scan_from_other_workspace_returns_404(client, db):
    _setup(client, db)
    _create_product_with_scans(client)
    scan_id = client.get("/api/scans").json()[0]["id"]
    client.post("/api/auth/logout")

    make_user(db, workspace_name="WS B", username="userB", password="passB123")
    login(client, "userB", "passB123")
    assert client.delete(f"/api/scans/{scan_id}").status_code == 404

    # El scan sigue existiendo en su workspace
    client.post("/api/auth/logout")
    login(client, "op", "secret123")
    assert len(client.get("/api/scans").json()) == 1


def test_delete_scan_requires_auth(client, db):
    _setup(client, db)
    _create_product_with_scans(client)
    scan_id = client.get("/api/scans").json()[0]["id"]
    client.post("/api/auth/logout")
    assert client.delete(f"/api/scans/{scan_id}").status_code == 401
