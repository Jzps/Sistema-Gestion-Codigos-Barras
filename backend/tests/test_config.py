"""Validación de la configuración de producción.

En producción la aplicación NO debe arrancar con la configuración insegura de
desarrollo: secreto JWT de ejemplo, cookies sin `Secure` o CORS apuntando a
localhost. Esta validación es la barrera que evita exponer sesiones falsificables
en un despliegue público.
"""

import pytest
from pydantic import ValidationError

from app.core.config import INSECURE_DEFAULT_SECRET, Settings

GOOD_SECRET = "a" * 64
PUBLIC_ORIGIN = "https://sgcbp-web.onrender.com"


def test_development_defaults_are_allowed():
    settings = Settings(ENV="development")
    assert settings.is_production is False
    assert settings.cors_origin_list


def test_production_with_valid_settings_is_accepted():
    settings = Settings(
        ENV="production",
        SECRET_KEY=GOOD_SECRET,
        COOKIE_SECURE=True,
        CORS_ORIGINS=PUBLIC_ORIGIN,
    )
    assert settings.is_production is True
    assert settings.cors_origin_list == [PUBLIC_ORIGIN]


def test_production_rejects_the_default_secret():
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENV="production",
            SECRET_KEY=INSECURE_DEFAULT_SECRET,
            COOKIE_SECURE=True,
            CORS_ORIGINS=PUBLIC_ORIGIN,
        )
    assert "SECRET_KEY" in str(exc.value)


def test_production_rejects_a_short_secret():
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENV="production",
            SECRET_KEY="corta",
            COOKIE_SECURE=True,
            CORS_ORIGINS=PUBLIC_ORIGIN,
        )
    assert "SECRET_KEY" in str(exc.value)


def test_production_requires_secure_cookies():
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENV="production",
            SECRET_KEY=GOOD_SECRET,
            COOKIE_SECURE=False,
            CORS_ORIGINS=PUBLIC_ORIGIN,
        )
    assert "COOKIE_SECURE" in str(exc.value)


def test_production_rejects_localhost_cors():
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENV="production",
            SECRET_KEY=GOOD_SECRET,
            COOKIE_SECURE=True,
            CORS_ORIGINS="http://localhost:4200",
        )
    assert "CORS_ORIGINS" in str(exc.value)


def test_production_requires_at_least_one_cors_origin():
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENV="production",
            SECRET_KEY=GOOD_SECRET,
            COOKIE_SECURE=True,
            CORS_ORIGINS="",
        )
    assert "CORS_ORIGINS" in str(exc.value)


def test_secure_cookie_flag_alone_also_triggers_the_check():
    """Activar COOKIE_SECURE ya implica un despliegue real: tambien se valida."""
    with pytest.raises(ValidationError):
        Settings(
            ENV="development",
            SECRET_KEY=INSECURE_DEFAULT_SECRET,
            COOKIE_SECURE=True,
            CORS_ORIGINS=PUBLIC_ORIGIN,
        )
