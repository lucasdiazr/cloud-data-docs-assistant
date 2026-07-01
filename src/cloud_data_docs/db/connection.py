"""Fábrica de conexiones a PostgreSQL (psycopg 3), síncronas y async.

Reglas de diseño:

- El módulo NO abre ninguna conexión en import-time. Todo ocurre bajo
  demanda al llamar a `get_connection()` / `get_async_connection()`.
- El DSN se construye desde `Settings` (pydantic-settings), nunca desde
  literales. Importante: `Settings.postgres_dsn` usa el formato SQLAlchemy
  (`postgresql+psycopg://`), que psycopg NO acepta. Aquí construimos el DSN
  nativo (`postgresql://`) a partir de los mismos campos.
"""

from __future__ import annotations

import psycopg

from cloud_data_docs.common.config import Settings, get_settings


def _build_dsn(settings: Settings) -> str:
    """Construye un DSN nativo de psycopg desde la configuración tipada."""
    password = settings.postgres_password.get_secret_value()
    return (
        f"postgresql://{settings.postgres_user}:{password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )


def get_connection() -> psycopg.Connection:
    """Abre y devuelve una conexión síncrona a PostgreSQL.

    El llamador es responsable de cerrarla (`conn.close()`) o de usarla como
    context manager (`with get_connection() as conn: ...`).
    """
    settings = get_settings()
    return psycopg.connect(_build_dsn(settings))


async def get_async_connection() -> psycopg.AsyncConnection:
    """Abre y devuelve una conexión asíncrona a PostgreSQL.

    El llamador es responsable de cerrarla (`await conn.close()`) o de usarla
    como async context manager (`async with await get_async_connection() ...`).
    """
    settings = get_settings()
    return await psycopg.AsyncConnection.connect(_build_dsn(settings))


__all__ = ["get_async_connection", "get_connection"]
