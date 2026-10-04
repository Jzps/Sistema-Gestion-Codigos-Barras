"""Seed de desarrollo: crea el workspace y el usuario admin iniciales.

Uso (desde backend/, con las migraciones ya aplicadas):
    python -m app.seed

Las credenciales se leen de variables de entorno (ver .env.example).
Los valores por defecto son SOLO para desarrollo local y estan documentados.
"""

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import User, Workspace


def main() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        workspace = db.scalar(
            select(Workspace).where(Workspace.name == settings.SEED_WORKSPACE_NAME)
        )
        if workspace is None:
            workspace = Workspace(name=settings.SEED_WORKSPACE_NAME)
            db.add(workspace)
            db.flush()
            print(f"Workspace creado: {workspace.name} (id={workspace.id})")
        else:
            print(f"Workspace ya existe: {workspace.name} (id={workspace.id})")

        user = db.scalar(
            select(User).where(User.username == settings.SEED_ADMIN_USERNAME)
        )
        if user is None:
            user = User(
                workspace_id=workspace.id,
                username=settings.SEED_ADMIN_USERNAME,
                email=settings.SEED_ADMIN_EMAIL,
                password_hash=hash_password(settings.SEED_ADMIN_PASSWORD),
                role="admin",
            )
            db.add(user)
            print(f"Usuario creado: {user.username} (rol=admin)")
        else:
            print(f"Usuario ya existe: {user.username}")

        db.commit()
        print("Seed completado.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
