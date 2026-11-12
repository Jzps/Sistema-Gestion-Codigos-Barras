from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.user import User


def get_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def update_password_hash(db: Session, user_id: int, password_hash: str) -> None:
    """Actualiza SOLO el hash de contrasena del usuario indicado.

    Se usa un UPDATE dirigido (no la asignacion de atributos del ORM) para
    que quede garantizado por construccion que ningun otro campo del usuario
    (workspace_id, username, email, role, is_active) se modifica. El commit
    lo hace el llamador.
    """
    db.execute(
        update(User)
        .where(User.id == user_id)
        .values(password_hash=password_hash)
        .execution_options(synchronize_session=False)
    )
