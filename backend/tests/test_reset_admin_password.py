"""Pruebas del comando `python -m app.reset_admin_password`.

Ninguna prueba toca la base de datos de produccion: todas usan la base
SQLite en memoria de `tests/conftest.py` y datos creados dentro del test.
"""

import pytest

from app.core.security import hash_password, verify_password
from app.reset_admin_password import (
    MIN_PASSWORD_LENGTH,
    PasswordPromptError,
    find_user,
    main,
    prompt_new_password,
    reset_admin_password,
    validate_new_password,
)
from tests.conftest import TestingSessionLocal, login, make_user

NEW_PASSWORD = "ClaveNuevaSegura2026!"


def _reader(values):
    """Devuelve un reader que va tentando valores de una lista."""
    remaining = list(values)

    def read(_prompt: str) -> str:
        return remaining.pop(0)

    return read


def test_reset_changes_only_the_password_hash(db):
    user = make_user(db, username="admin")
    before = {
        "workspace_id": user.workspace_id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "password_hash": user.password_hash,
    }

    updated = reset_admin_password(db, username="admin", new_password=NEW_PASSWORD)

    # El hash es lo UNICO que cambia.
    assert updated.password_hash != before["password_hash"]
    assert updated.workspace_id == before["workspace_id"]
    assert updated.username == before["username"]
    assert updated.email == before["email"]
    assert updated.role == before["role"]
    assert updated.is_active == before["is_active"]
    assert updated.created_at == before["created_at"]


def test_new_hash_is_argon2id_and_validates_the_new_password(db):
    user = make_user(db, username="admin")
    old_hash = user.password_hash

    updated = reset_admin_password(db, username="admin", new_password=NEW_PASSWORD)

    # Mismo formato/mecanismo que usa la aplicacion (argon2-cffi / Argon2id).
    assert updated.password_hash.startswith("$argon2id$")
    assert updated.password_hash != old_hash
    assert verify_password(NEW_PASSWORD, updated.password_hash) is True
    # La contrasena anterior deja de servir.
    assert verify_password("secret123", updated.password_hash) is False


def test_reset_does_not_touch_other_users(db):
    admin = make_user(db, username="admin")
    other = make_user(
        db, username="operador", email="op@test.dev", workspace_name="WS Otro"
    )
    other_hash = other.password_hash

    reset_admin_password(db, username="admin", new_password=NEW_PASSWORD)

    db.refresh(other)
    assert other.password_hash == other_hash
    assert admin.password_hash != other_hash


def test_reset_allows_login_with_the_new_password(client, db):
    make_user(db, username="admin", password="claveVieja123456")
    reset_admin_password(db, username="admin", new_password=NEW_PASSWORD)

    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": NEW_PASSWORD}
    )
    assert response.status_code == 200, response.text

    old = client.post(
        "/api/auth/login", json={"username": "admin", "password": "claveVieja123456"}
    )
    assert old.status_code == 401


def test_reset_unknown_user_raises_and_changes_nothing(db):
    make_user(db, username="admin")
    admin = find_user(db, "admin")
    hash_before = admin.password_hash

    with pytest.raises(LookupError):
        reset_admin_password(db, username="no-existe", new_password=NEW_PASSWORD)

    db.refresh(admin)
    assert admin.password_hash == hash_before


def test_reset_rejects_a_short_password_without_touching_the_db(db):
    admin = make_user(db, username="admin")
    hash_before = admin.password_hash

    with pytest.raises(ValueError):
        reset_admin_password(db, username="admin", new_password="corta")

    db.refresh(admin)
    assert admin.password_hash == hash_before


def test_validate_new_password_rules():
    assert validate_new_password(NEW_PASSWORD, NEW_PASSWORD) == NEW_PASSWORD
    with pytest.raises(ValueError):
        validate_new_password("corta", "corta")
    with pytest.raises(ValueError):
        validate_new_password(NEW_PASSWORD, NEW_PASSWORD + "distinta")


def test_prompt_returns_the_password_when_confirmed(capsys):
    read = _reader([NEW_PASSWORD, NEW_PASSWORD])

    result = prompt_new_password(read)

    assert result == NEW_PASSWORD
    # La contrasena no se imprime por pantalla.
    assert NEW_PASSWORD not in capsys.readouterr().out


def test_prompt_rejects_a_short_password_and_retries(capsys):
    read = _reader(["corta", NEW_PASSWORD, NEW_PASSWORD])

    result = prompt_new_password(read)

    assert result == NEW_PASSWORD
    output = capsys.readouterr().out
    assert str(MIN_PASSWORD_LENGTH) in output
    # El prompt de confirmacion no se pidio para la contrasena corta.
    assert "Repite" not in output


def test_prompt_rejects_mismatched_confirmation_and_retries(capsys):
    read = _reader([NEW_PASSWORD, "OtraClaveDistinta9!", NEW_PASSWORD, NEW_PASSWORD])

    result = prompt_new_password(read)

    assert result == NEW_PASSWORD
    assert "no coinciden" in capsys.readouterr().out


def test_prompt_gives_up_after_max_attempts():
    read = _reader(["corta"] * 6)

    with pytest.raises(PasswordPromptError):
        prompt_new_password(read, max_attempts=2)


def test_find_user_raises_when_missing(db):
    with pytest.raises(LookupError):
        find_user(db, "no-existe")


def test_main_updates_the_password_and_never_prints_credentials(
    monkeypatch, capsys, db
):
    admin = make_user(db, username="admin", password="claveVieja123456")
    hash_before = admin.password_hash
    monkeypatch.setattr(
        "app.reset_admin_password.SessionLocal", lambda: TestingSessionLocal()
    )
    monkeypatch.setattr(
        "app.reset_admin_password.getpass.getpass", _reader([NEW_PASSWORD, NEW_PASSWORD])
    )

    exit_code = main(["--username", "admin"])

    assert exit_code == 0
    db.refresh(admin)
    assert admin.password_hash != hash_before
    assert verify_password(NEW_PASSWORD, admin.password_hash) is True

    output = capsys.readouterr().out
    assert NEW_PASSWORD not in output
    assert admin.password_hash not in output
    assert "hash de contrasena" in output


def test_main_with_unknown_user_changes_nothing_and_does_not_prompt(
    monkeypatch, capsys, db
):
    make_user(db, username="admin")
    admin = find_user(db, "admin")
    hash_before = admin.password_hash
    calls = []

    def reader(_prompt: str) -> str:
        calls.append(_prompt)
        return NEW_PASSWORD

    monkeypatch.setattr("app.reset_admin_password.SessionLocal", lambda: TestingSessionLocal())
    monkeypatch.setattr("app.reset_admin_password.getpass.getpass", reader)

    exit_code = main(["--username", "no-existe"])

    assert exit_code == 1
    assert calls == []  # no se pide ninguna contrasena
    db.refresh(admin)
    assert admin.password_hash == hash_before
    assert "No se ha modificado nada" in capsys.readouterr().out


def test_main_uses_admin_by_default(monkeypatch, db):
    admin = make_user(db, username="admin")
    monkeypatch.setattr("app.reset_admin_password.SessionLocal", lambda: TestingSessionLocal())
    monkeypatch.setattr(
        "app.reset_admin_password.getpass.getpass", _reader([NEW_PASSWORD, NEW_PASSWORD])
    )
    # Sin argumentos, el comando actua sobre el usuario "admin".
    monkeypatch.setattr("sys.argv", ["python -m app.reset_admin_password"])

    assert main() == 0
    db.refresh(admin)
    assert verify_password(NEW_PASSWORD, admin.password_hash) is True


def test_reset_uses_the_same_hasher_as_the_application(db):
    """El hash generado debe ser verificable con el verificador de la app."""
    make_user(db, username="admin")
    updated = reset_admin_password(db, username="admin", new_password=NEW_PASSWORD)

    reference = hash_password(NEW_PASSWORD)

    assert updated.password_hash.split("$")[1] == reference.split("$")[1]
    assert verify_password(NEW_PASSWORD, updated.password_hash) == verify_password(
        NEW_PASSWORD, reference
    )


def test_login_still_works_after_reset_through_the_api(client, db):
    """El flujo completo de login sigue operativo tras el cambio."""
    make_user(db, username="admin", password="claveVieja123456")
    login(client, "admin", "claveVieja123456")

    reset_admin_password(db, username="admin", new_password=NEW_PASSWORD)

    ok = client.post(
        "/api/auth/login", json={"username": "admin", "password": NEW_PASSWORD}
    )
    assert ok.status_code == 200
    assert "password_hash" not in ok.text
