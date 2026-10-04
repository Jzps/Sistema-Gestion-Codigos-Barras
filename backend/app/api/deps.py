"""Dependencias FastAPI compartidas.

`get_current_user` es el unico punto donde se resuelve la identidad:
lee el JWT de la cookie HttpOnly y carga el usuario desde la BD.
El workspace SIEMPRE se deriva del usuario autenticado, nunca del cliente.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(request: Request, db: DbSession) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
    )
    token = request.cookies.get(get_settings().COOKIE_NAME)
    if not token:
        raise credentials_error
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise credentials_error
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise credentials_error from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
