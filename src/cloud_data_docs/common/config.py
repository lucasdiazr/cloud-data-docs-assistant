"""Configuración tipada del proyecto cargada desde .env.

Uso típico:

    from cloud_data_docs.common.config import get_settings

    settings = get_settings()
    print(settings.postgres_dsn)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables de entorno de la aplicación, validadas con Pydantic."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM providers ---
    anthropic_api_key: SecretStr = Field(..., alias="ANTHROPIC_API_KEY")
    openai_api_key: SecretStr = Field(..., alias="OPENAI_API_KEY")
    cohere_api_key: SecretStr = Field(..., alias="COHERE_API_KEY")

    # --- PostgreSQL ---
    postgres_user: str = Field(..., alias="POSTGRES_USER")
    postgres_password: SecretStr = Field(..., alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(..., alias="POSTGRES_DB")
    postgres_host: str = Field("localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")

    # --- Langfuse ---
    langfuse_public_key: SecretStr | None = Field(None, alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: SecretStr | None = Field(None, alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field("http://localhost:3000", alias="LANGFUSE_HOST")

    # --- Aplicación ---
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        "INFO", alias="LOG_LEVEL"
    )
    app_env: Literal["development", "staging", "production"] = Field(
        "development", alias="APP_ENV"
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def postgres_dsn(self) -> str:
        """DSN de PostgreSQL en formato esperado por psycopg/SQLAlchemy."""
        password = self.postgres_password.get_secret_value()
        return (
            f"postgresql+psycopg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Devuelve la instancia (cacheada) de Settings.

    El uso de `lru_cache` garantiza que .env se lee una sola vez por proceso.
    """
    return Settings()  # type: ignore[call-arg]
