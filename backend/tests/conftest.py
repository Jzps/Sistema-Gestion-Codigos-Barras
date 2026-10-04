"""Fixtures de pytest.

Los tests usan SQLite en memoria (rapido y sin Docker). El esquema real en
desarrollo/produccion lo gestiona Alembic contra PostgreSQL; aqui se usa
Base.metadata.create_all solo como atajo de test.
"""

import os

# Antes de importar cualquier modulo de la app: nunca tocar la BD real.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret-key-with-64-chars-padding-for-hmac-sha256-0000"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models import User, Workspace  # noqa: F401 (registra modelos)

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db():
    Base.metadata.create_all(engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Limpieza entre tests, respetando FKs.
        with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())


@pytest.fixture()
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_user(
    db,
    *,
    workspace_name: str = "WS Test",
    username: str = "user1",
    password: str = "secret123",
    email: str | None = None,
) -> User:
    workspace = Workspace(name=workspace_name)
    db.add(workspace)
    db.flush()
    user = User(
        workspace_id=workspace.id,
        username=username,
        email=email or f"{username}@test.dev",
        password_hash=hash_password(password),
        role="operator",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(client: TestClient, username: str, password: str) -> None:
    response = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
