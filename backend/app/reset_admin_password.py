"""Cambio interactivo y seguro de la contrasena de un usuario existente.

Uso (desde backend/, con las migraciones aplicadas y `DATABASE_URL` apuntando
a la base de datos correcta):

    python -m app.reset_admin_password
    python -m app.reset_admin_password --username admin

Como funciona:
  1. Conecta con `DATABASE_URL` (misma fuente que la aplicacion).
  2. Comprueba que el usuario existe. Si no existe, aborta SIN preguntar nada
     y SIN tocar la base de datos.
  3. Pide la nueva contrasena dos veces por consola, sin eco en pantalla
     (getpass). La longitud minima es de 1 caracter.
  4. Genera el hash con el MISMO mecanismo que usa la aplicacion
     (`app.core.security.hash_password`, Argon2id).
  5. Actualiza UNICAMENTE el hash de contrasena de ese usuario. No toca el
     workspace, el rol, el email ni ningun otro dato.
  6. Confirma el exito sin mostrar jamas la contrasena ni su hash.

La contrasena NO se escribe en ningun archivo, no se lee de ninguna variable
de entorno y no se imprime ni se registra en ningun log.

Este comando no cambia el sistema de autenticacion: solo reescribe el hash
guardado, que es exactamente lo que haria un "cambio de contrasena" en la
aplicacion.
"""

import argparse
import getpass
import sys
import warnings
from collections.abc import Callable

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories import users as users_repo

#: Longitud minima de la nueva contrasena.
MIN_PASSWORD_LENGTH = 1

#: Usuario por defecto (el creado por `python -m app.seed`).
DEFAULT_USERNAME = "admin"

#: Intentos maximos de introducir una contrasena valida.
MAX_ATTEMPTS = 3


class PasswordPromptError(Exception):
    """El usuario no ha conseguido introducir una contrasena valida."""


def min_length_text(min_length: int = MIN_PASSWORD_LENGTH) -> str:
    """Describe el minimo de longitud en singular o plural."""
    unit = "caracter" if min_length == 1 else "caracteres"
    return f"{min_length} {unit}"


def validate_password_length(password: str) -> None:
    """Comprueba la longitud minima. Lanza ValueError si no se cumple."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"La contrasena debe tener al menos {min_length_text()} "
            f"(introducidos: {len(password)})."
        )


def validate_new_password(password: str, confirmation: str) -> str:
    """Valida longitud minima y coincidencia de las dos entradas.

    Devuelve la contrasena validada. Lanza ValueError si no cumple las
    reglas. No imprime ni registra nada.
    """
    validate_password_length(password)
    if password != confirmation:
        raise ValueError("Las contrasenas no coinciden.")
    return password


def prompt_new_password(
    reader: Callable[[str], str] | None = None,
    *,
    printer: Callable[[str], None] = print,
    min_length: int = MIN_PASSWORD_LENGTH,
    max_attempts: int = MAX_ATTEMPTS,
) -> str:
    """Solicita la nueva contrasena por consola, sin eco, y la confirma.

    `reader` recibe el texto del prompt y devuelve lo tecleado. Por defecto
    se usa `getpass.getpass`, que desactiva el eco en la terminal.
    """
    read = reader or _hidden_reader
    for attempt in range(1, max_attempts + 1):
        remaining = max_attempts - attempt + 1
        password = read("Nueva contrasena: ")
        if len(password) < min_length:
            printer(
                f"[!] La contrasena debe tener al menos {min_length_text(min_length)}. "
                f"Te quedan {remaining} intento(s)."
            )
            continue
        confirmation = read("Repite la nueva contrasena: ")
        if password != confirmation:
            printer(
                f"[!] Las contrasenas no coinciden. Te quedan {remaining} intento(s)."
            )
            continue
        return password
    raise PasswordPromptError(
        f"No se ha podido introducir una contrasena valida en {max_attempts} intentos."
    )


def _hidden_reader(prompt: str) -> str:
    """Lee una linea sin eco; avisa si la terminal no puede ocultarla."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", getpass.GetPassWarning)
        value = getpass.getpass(prompt)
    for warning in caught:
        if issubclass(warning.category, getpass.GetPassWarning):
            print(
                "[!] Aviso: esta terminal no permite ocultar lo que escribes; "
                "la contrasena puede quedar visible en pantalla."
            )
    return value


def find_user(db: Session, username: str) -> User:
    """Devuelve el usuario o lanza LookupError si no existe."""
    user = users_repo.get_by_username(db, username)
    if user is None:
        raise LookupError(f"No existe ningun usuario con el nombre '{username}'.")
    return user


def reset_admin_password(db: Session, *, username: str, new_password: str) -> User:
    """Actualiza SOLO el hash de contrasena del usuario existente.

    No modifica el workspace, el rol, el email, el estado ni ningun otro dato
    del usuario. Si algo falla, la transaccion se deshace y la base de datos
    queda intacta.
    """
    validate_password_length(new_password)
    user = find_user(db, username)

    new_hash = hash_password(new_password)
    # Se valida el hash recien creado ANTES de tocar la base de datos: si algo
    # va mal, no se escribe nada.
    if not verify_password(new_password, new_hash):
        db.rollback()
        raise RuntimeError(
            "El hash generado no valida la contrasena; no se ha modificado nada."
        )

    try:
        users_repo.update_password_hash(db, user.id, new_hash)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    db.refresh(user)
    # Comprobacion final sobre lo que ha quedado realmente en la base de datos.
    if not verify_password(new_password, user.password_hash):
        raise RuntimeError(
            "La contrasena no valida despues de guardarla; revisa la base de datos."
        )
    return user


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.reset_admin_password",
        description=(
            "Cambia la contrasena de un usuario existente. La nueva contrasena se "
            "pide por consola (sin eco) y se confirma dos veces."
        ),
    )
    parser.add_argument(
        "--username",
        default=DEFAULT_USERNAME,
        help=f"Usuario a actualizar (por defecto: {DEFAULT_USERNAME}).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada. Devuelve el codigo de salida del proceso."""
    args = _parse_args(argv)

    # 1. Comprobar que el usuario existe ANTES de pedir la contrasena.
    db = SessionLocal()
    try:
        user = find_user(db, args.username)
        workspace_name = user.workspace.name
        print(f"Usuario encontrado: {user.username} (rol={user.role})")
        print(f"Workspace: {workspace_name}")
    except LookupError as exc:
        print(f"[X] {exc}")
        print("    No se ha modificado nada.")
        return 1
    finally:
        db.close()

    # 2. Pedir la nueva contrasena (interactivo, sin eco).
    print()
    print(f"Nueva contrasena para '{args.username}' (minimo {min_length_text()}):")
    try:
        new_password = prompt_new_password()
    except PasswordPromptError as exc:
        print(f"[X] {exc}")
        print("    No se ha modificado nada.")
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nOperacion cancelada. No se ha modificado nada.")
        return 130

    # 3. Actualizar SOLO el hash.
    db = SessionLocal()
    try:
        updated = reset_admin_password(
            db, username=args.username, new_password=new_password
        )
    except LookupError as exc:
        print(f"[X] {exc}")
        print("    No se ha modificado nada.")
        return 1
    except ValueError as exc:
        print(f"[X] {exc}")
        print("    No se ha modificado nada.")
        return 1
    except SQLAlchemyError as exc:
        print(f"[X] Error de base de datos: {exc}")
        print("    No se ha modificado nada.")
        return 1
    except Exception as exc:  # noqa: BLE001 - ultimo recurso, sin traza
        print(f"[X] Error inesperado: {exc}")
        print("    No se ha modificado nada.")
        return 1
    finally:
        db.close()

    # 4. Confirmacion. Nunca se imprime la contrasena ni su hash.
    print()
    print(f"[OK] Contrasena actualizada para el usuario '{updated.username}'.")
    print("     Solo se ha modificado el hash de contrasena.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
