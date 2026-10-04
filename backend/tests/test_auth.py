"""Autenticacion: login, logout, sesion y proteccion de endpoints."""

from tests.conftest import login, make_user


def test_login_ok_sets_cookie_and_returns_user(client, db):
    make_user(db, username="admin", password="admin123", workspace_name="WS Auth")
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["username"] == "admin"
    assert body["user"]["workspace_name"] == "WS Auth"
    assert "password_hash" not in body["user"]
    assert "sgcbp_session" in response.cookies


def test_login_wrong_password_rejected(client, db):
    make_user(db, username="admin", password="admin123")
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": "wrong"}
    )
    assert response.status_code == 401


def test_me_without_session_is_unauthorized(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_with_session_returns_current_user(client, db):
    make_user(db, username="admin", password="admin123")
    login(client, "admin", "admin123")
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["username"] == "admin"


def test_logout_invalidates_session(client, db):
    make_user(db, username="admin", password="admin123")
    login(client, "admin", "admin123")
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_protected_endpoints_require_auth(client):
    assert client.get("/api/scans").status_code == 401
    assert client.post("/api/scans", json={"barcode": "123"}).status_code == 401
    assert client.get("/api/products").status_code == 401
    assert client.get("/api/products/1").status_code == 401
    assert client.get("/api/reports/scans.xlsx").status_code == 401


def test_health_is_public(client):
    assert client.get("/api/health").status_code == 200
