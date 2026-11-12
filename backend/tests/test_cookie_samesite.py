"""Pruebas del atributo SameSite de la cookie de sesion.

Contexto del problema resuelto: en Render, el frontend (`sgcbp-web.onrender.com`)
y la API (`sgcbp-api.onrender.com`) estan en sitios cross-site (porque
"onrender.com" esta en la Public Suffix List). Con `SameSite=lax` el
navegador NO envia la cookie en las peticiones XHR cross-site -> 401 en
todos los endpoints protegidos aunque el login haya funcionado.

`COOKIE_SAMESITE=none` (con `COOKIE_SECURE=true`) permite el envio cross-site.
"""

import pytest
from pydantic import ValidationError

from app.api.routes import auth
from app.core.config import Settings
from tests.conftest import make_user


def _settings(**overrides) -> Settings:
    """Ajustes de configuracion para los tests de la cookie.

    Con COOKIE_SECURE=true la aplicacion entra en modo produccion estricto
    (CORS publico obligatorio), asi que el helper lo ajusta para poder
    probar la cookie con Secure y SameSite=None.
    """
    base = {
        "ENV": "development",
        "SECRET_KEY": "s" * 64,
        "COOKIE_SECURE": False,
        "COOKIE_SAMESITE": "lax",
        "CORS_ORIGINS": "http://localhost:4200",
        "DATABASE_URL": "sqlite://",
    }
    base.update(overrides)
    if base["COOKIE_SECURE"] and base["CORS_ORIGINS"].startswith("http://localhost"):
        base["CORS_ORIGINS"] = "https://sgcbp-web.onrender.com"
    return Settings(**base)


# --- Emision de la cookie ----------------------------------------------------


def test_login_sets_samesite_none_when_configured(monkeypatch, client, db):
    make_user(db, username="admin", password="secret123")
    monkeypatch.setattr(
        auth, "get_settings", lambda: _settings(COOKIE_SAMESITE="none", COOKIE_SECURE=True)
    )

    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret123"}
    )

    assert response.status_code == 200, response.text
    cookie = response.headers["set-cookie"]
    assert "SameSite=none" in cookie
    # El resto de atributos se conservan intactos.
    assert "HttpOnly" in cookie
    assert "Path=/" in cookie
    assert "Secure" in cookie
    assert "Max-Age=43200" in cookie  # ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert "sgcbp_session=" in cookie


def test_login_default_samesite_is_lax(monkeypatch, client, db):
    """Sin configuracion explicita, la cookie se emite con SameSite=lax."""
    make_user(db, username="admin", password="secret123")
    monkeypatch.setattr(auth, "get_settings", lambda: _settings())

    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret123"}
    )

    assert response.status_code == 200, response.text
    cookie = response.headers["set-cookie"]
    assert "SameSite=lax" in cookie
    assert "Secure" not in cookie


def test_login_samesite_strict_is_emitted(monkeypatch, client, db):
    make_user(db, username="admin", password="secret123")
    monkeypatch.setattr(
        auth, "get_settings", lambda: _settings(COOKIE_SAMESITE="strict", COOKIE_SECURE=True)
    )

    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret123"}
    )

    assert response.status_code == 200, response.text
    assert "SameSite=strict" in response.headers["set-cookie"]


# --- Eliminacion de la cookie (logout) ---------------------------------------


def test_logout_deletes_cookie_with_the_same_samesite(monkeypatch, client):
    monkeypatch.setattr(
        auth, "get_settings", lambda: _settings(COOKIE_SAMESITE="none", COOKIE_SECURE=True)
    )

    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    cookie = response.headers["set-cookie"]
    assert "SameSite=none" in cookie
    # La cookie se invalida de inmediato y con los mismos atributos.
    assert "Max-Age=0" in cookie
    assert "Path=/" in cookie
    assert "Secure" in cookie
    assert "HttpOnly" in cookie


def test_logout_deletes_cookie_with_lax_by_default(monkeypatch, client):
    monkeypatch.setattr(auth, "get_settings", lambda: _settings())

    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    cookie = response.headers["set-cookie"]
    assert "SameSite=lax" in cookie
    assert "Max-Age=0" in cookie


def test_logout_uses_the_same_samesite_as_login(monkeypatch, client, db):
    """La cookie que se borra debe ser identica (en atributos) a la emitida."""
    make_user(db, username="admin", password="secret123")
    monkeypatch.setattr(
        auth, "get_settings", lambda: _settings(COOKIE_SAMESITE="none", COOKIE_SECURE=True)
    )

    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret123"}
    )
    logout = client.post("/api/auth/logout")

    def attributes(header: str) -> dict[str, str]:
        # Se comparan los atributos, no el valor (el token es distinto).
        result = {}
        for part in header.split("; "):
            if "=" in part and not part.startswith("sgcbp_session="):
                key, _, value = part.partition("=")
                result[key.strip()] = value.strip()
        return result

    login_attrs = attributes(login.headers["set-cookie"])
    logout_attrs = attributes(logout.headers["set-cookie"])
    for key in ("Path", "SameSite", "Secure", "HttpOnly"):
        assert login_attrs.get(key) == logout_attrs.get(key), key


# --- Configuracion -----------------------------------------------------------


def test_default_configuration_samesite_is_lax():
    settings = Settings(ENV="development")
    assert settings.COOKIE_SAMESITE == "lax"
    assert settings.COOKIE_SECURE is False


def test_samesite_none_requires_secure_cookie():
    """SameSite=None sin Secure es incoherente: el navegador la descarta."""
    with pytest.raises(ValidationError) as exc:
        Settings(ENV="development", COOKIE_SAMESITE="none", COOKIE_SECURE=False)
    message = str(exc.value)
    assert "COOKIE_SECURE" in message
    assert "COOKIE_SAMESITE=none" in message


def test_samesite_none_is_accepted_with_secure_cookie():
    settings = _settings(COOKIE_SAMESITE="none", COOKIE_SECURE=True)
    assert settings.COOKIE_SAMESITE == "none"
    assert settings.COOKIE_SECURE is True


def test_samesite_none_is_accepted_in_production():
    settings = Settings(
        ENV="production",
        SECRET_KEY="p" * 64,
        COOKIE_SAMESITE="none",
        COOKIE_SECURE=True,
        CORS_ORIGINS="https://sgcbp-web.onrender.com",
    )
    assert settings.COOKIE_SAMESITE == "none"


@pytest.mark.parametrize("value", ["whatever", "LAX-NONE", "None2", "lax none", "1"])
def test_invalid_samesite_values_are_rejected(value):
    with pytest.raises(ValidationError) as exc:
        Settings(ENV="development", COOKIE_SAMESITE=value)
    assert "COOKIE_SAMESITE" in str(exc.value)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("lax", "lax"), ("LAX", "lax"), ("None", "none"), (" none ", "none"), ("STRICT", "strict")],
)
def test_samesite_value_is_normalized(raw, expected):
    settings = _settings(COOKIE_SAMESITE=raw, COOKIE_SECURE=True)
    assert settings.COOKIE_SAMESITE == expected


def test_samesite_none_without_secure_is_rejected_even_in_development():
    """La regla none -> secure no depende de ENV: siempre se aplica."""
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENV="development",
            SECRET_KEY="s" * 64,
            COOKIE_SAMESITE="None",
            COOKIE_SECURE=False,
            CORS_ORIGINS="http://localhost:4200",
        )
    assert "COOKIE_SECURE" in str(exc.value)


# --- El flujo completo sigue funcionando ------------------------------------


def test_login_and_protected_endpoints_still_work(monkeypatch, client, db):
    """Login -> endpoints protegidos -> logout, con SameSite=none.

    El cookie jar de httpx no guarda cookies "Secure" sobre http://testserver
    (artefacto del cliente de test, no del codigo), asi que la cookie se
    reenvia manualmente, que es exactamente lo que haria el navegador.
    """
    make_user(db, username="admin", password="secret123")
    monkeypatch.setattr(
        auth, "get_settings", lambda: _settings(COOKIE_SAMESITE="none", COOKIE_SECURE=True)
    )

    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret123"}
    )
    assert login.status_code == 200, login.text
    assert "SameSite=none" in login.headers["set-cookie"]

    token = login.headers["set-cookie"].split(";")[0].split("=", 1)[1]
    cookie_header = {"Cookie": f"sgcbp_session={token}"}

    me = client.get("/api/auth/me", headers=cookie_header)
    assert me.status_code == 200
    assert me.json()["username"] == "admin"

    products = client.get("/api/products", headers=cookie_header)
    assert products.status_code == 200
    assert isinstance(products.json(), list)

    scans = client.get("/api/scans", headers=cookie_header)
    assert scans.status_code == 200

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204

    # Tras el logout la cookie se invalida y el endpoint protegido responde 401.
    assert client.get("/api/auth/me").status_code == 401


def test_default_flow_login_products_scans_logout(monkeypatch, client, db):
    """El flujo habitual (SameSite=lax, sin Secure) sigue intacto."""
    make_user(db, username="admin", password="secret123")
    monkeypatch.setattr(auth, "get_settings", lambda: _settings())

    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret123"}
    )
    assert login.status_code == 200, login.text
    assert "SameSite=lax" in login.headers["set-cookie"]

    assert client.get("/api/auth/me").status_code == 200
    assert client.get("/api/products").status_code == 200
    assert client.get("/api/scans").status_code == 200

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204
    assert client.get("/api/auth/me").status_code == 401
