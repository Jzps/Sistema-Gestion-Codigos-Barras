"""Configuracion central de la aplicacion.

Toda la configuracion sensible llega por variables de entorno (o archivo .env).
Ver .env.example en la raiz del repositorio.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Se busca .env en el directorio actual (backend/) y en la raiz del repo.
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Base de datos
    DATABASE_URL: str = "postgresql+psycopg://sgcbp:sgcbp@localhost:5432/sgcbp"

    # Seguridad / sesion
    # Clave dev de >=32 bytes para evitar avisos de HMAC; cambiar en .env real.
    SECRET_KEY: str = "dev-only-insecure-key-change-me-32b"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720
    COOKIE_NAME: str = "sgcbp_session"
    COOKIE_SECURE: bool = False  # True obligatorio en produccion (HTTPS)

    # CORS: lista separada por comas
    CORS_ORIGINS: str = "http://localhost:4200,http://127.0.0.1:4200"

    ENV: str = "development"

    # Seed de desarrollo (solo datos de ejemplo)
    SEED_WORKSPACE_NAME: str = "Demo Workspace"
    SEED_ADMIN_USERNAME: str = "admin"
    SEED_ADMIN_EMAIL: str = "admin@example.com"
    SEED_ADMIN_PASSWORD: str = "admin123"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
