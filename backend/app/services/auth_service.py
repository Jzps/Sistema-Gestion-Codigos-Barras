from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.user import User
from app.repositories import users as users_repo


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    """Devuelve el usuario si las credenciales son validas y esta activo."""
    user = users_repo.get_by_username(db, username)
    if user is None:
        # Misma respuesta que contrasena incorrecta: no revelar si el usuario existe.
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None
    return user
