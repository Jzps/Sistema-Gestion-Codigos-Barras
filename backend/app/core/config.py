"""Configuracion central de la aplicacion.

Toda la configuracion sensible llega por variables de entorno (o archivo .env).
Ver .env.example en la raiz del repositorio.

En produccion (Render) la validacion es estricta: si `ENV=production` (o si se
activa `COOKIE_SECURE`) la aplicacion NO arranca con la configuracion insegura
de desarrollo. Es una salvaguarda para que un despliegue no expose sesiones
firmadas con una clave publica del repositorio.
"""

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Clave de desarrollo: publica y NO debe usarse en produccion.
INSECURE_DEFAULT_SECRET = "dev-only-insecure-key-change-me-32b"
MIN_SECRET_LENGTH = 32

# Origenes que nunca son validos para una app servida por internet.
LOCAL_ORIGINS = ("localhost", "127.0.0.1", "0.0.0.0", "[::1]")

# Valores admitidos para el atributo SameSite de la cookie de sesion.
VALID_COOKIE_SAMESITE = ("lax", "none", "strict")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Se busca .env en el directorio actual (backend/) y en la raiz del repo.
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Base de datos
    # En Neon: postgresql+psycopg://USER:PASSWORD@ep-xxx-pooler.REGION.aws.neon.tech/DBNAME?sslmode=require
    DATABASE_URL: str = "postgresql+psycopg://sgcbp:sgcbp@localhost:5432/sgcbp"

    # Seguridad / sesion
    # Clave dev de >=32 bytes para evitar avisos de HMAC; cambiar en .env real.
    SECRET_KEY: str = INSECURE_DEFAULT_SECRET
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720
    COOKIE_NAME: str = "sgcbp_session"
    COOKIE_SECURE: bool = False  # True obligatorio en produccion (HTTPS)
    # Atributo SameSite de la cookie de sesion.
    # - "lax" (por defecto): el navegador solo envia la cookie en peticiones
    #   del mismo sitio. Es lo correcto en local y en despliegues de un solo
    #   origen.
    # - "none": permite enviar la cookie en peticiones cross-site. Necesario
    #   cuando el frontend y la API estan en sitios distintos (p. ej.
    #   sgcbp-web.onrender.com y sgcbp-api.onrender.com: al estar
    #   "onrender.com" en la Public Suffix List, son sitios distintos y con
    #   "lax" el navegador NO envia la cookie -> 401 en los endpoints
    #   protegidos). Exige COOKIE_SECURE=true.
    # - "strict": la cookie nunca se envia en peticiones cross-site.
    COOKIE_SAMESITE: str = "lax"

    # CORS: lista separada por comas
    CORS_ORIGINS: str = "http://localhost:4200,http://127.0.0.1:4200"

    # Entorno: "development" | "production". En "production" la configuracion
    # insegura de desarrollo hace fallar el arranque (ver _check_production).
    ENV: str = "development"

    # Servidor: Render asigna PORT y exige escuchar en 0.0.0.0.
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Seed de desarrollo (solo datos de ejemplo)
    SEED_WORKSPACE_NAME: str = "Demo Workspace"
    SEED_ADMIN_USERNAME: str = "admin"
    SEED_ADMIN_EMAIL: str = "admin@example.com"
    SEED_ADMIN_PASSWORD: str = "admin123"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENV.strip().lower() == "production"

    @field_validator("COOKIE_SAMESITE", mode="before")
    @classmethod
    def _validate_cookie_samesite(cls, value: object) -> str:
        """Solo se admiten lax, none y strict (sin distinguir mayusculas)."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in VALID_COOKIE_SAMESITE:
                return normalized
            raise ValueError(
                "COOKIE_SAMESITE debe ser uno de: "
                f"{', '.join(VALID_COOKIE_SAMESITE)} (valor recibido: {value!r})"
            )
        raise ValueError(
            "COOKIE_SAMESITE debe ser una cadena con uno de: "
            f"{', '.join(VALID_COOKIE_SAMESITE)}"
        )

    @model_validator(mode="after")
    def _check_production(self) -> "Settings":
        """Impide arrancar con una configuracion de sesion incoherente.

        - Always: `COOKIE_SAMESITE=none` exige `COOKIE_SECURE=true`. Los
          navegadores rechazan una cookie SameSite=None sin Secure, y sin
          Secure la cookie no viaja en HTTPS: la sesion no funcionaria.
        - En produccion (ENV=production o COOKIE_SECURE=true): ademas se
          exige un SECRET_KEY propio, cookies seguras y CORS publico.

        El proceso muere al importar la app: es preferible a servir
        sesiones que el navegador va a descartar o falsificables.
        """
        problems: list[str] = []

        if self.COOKIE_SAMESITE == "none" and not self.COOKIE_SECURE:
            problems.append(
                "COOKIE_SAMESITE=none exige COOKIE_SECURE=true "
                "(los navegadores rechazan una cookie SameSite=None sin Secure)"
            )

        if self.is_production or self.COOKIE_SECURE:
            if self.SECRET_KEY == INSECURE_DEFAULT_SECRET:
                problems.append(
                    "SECRET_KEY sigue siendo la clave de desarrollo; define una propia "
                    f"(python -c \"import secrets; print(secrets.token_hex(32))\")"
                )
            elif len(self.SECRET_KEY) < MIN_SECRET_LENGTH:
                problems.append(
                    f"SECRET_KEY debe tener al menos {MIN_SECRET_LENGTH} caracteres"
                )

            if not self.COOKIE_SECURE:
                problems.append(
                    "COOKIE_SECURE debe ser true en produccion (la cookie necesita HTTPS)"
                )

            origins = self.cors_origin_list
            if not origins:
                problems.append("CORS_ORIGINS debe incluir el dominio publico del frontend")
            elif any(
                any(local in origin.lower() for local in LOCAL_ORIGINS)
                for origin in origins
            ):
                problems.append(
                    "CORS_ORIGINS no puede apuntar a localhost en produccion; "
                    "usa el dominio publico del frontend"
                )

        if problems:
            prefix = (
                "Configuracion de produccion invalida: "
                if (self.is_production or self.COOKIE_SECURE)
                else "Configuracion invalida: "
            )
            raise ValueError(prefix + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
