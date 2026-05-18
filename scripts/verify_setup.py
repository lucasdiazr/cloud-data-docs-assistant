"""Verifica el setup local de PostgreSQL + pgvector.

Conecta a la base de datos usando las credenciales del .env (cargadas vía
pydantic-settings) y comprueba que las extensiones `vector` y `pg_trgm`
están instaladas. Reporta el resultado por stdout y termina con código
de salida 0 si todo está OK, 1 en caso contrario.

Uso:
    uv run python scripts/verify_setup.py
"""

from __future__ import annotations

import sys

import psycopg

from cloud_data_docs.common.config import get_settings

REQUIRED_EXTENSIONS = ("vector", "pg_trgm")


def main() -> int:
    settings = get_settings()
    dsn = (
        f"host={settings.postgres_host} "
        f"port={settings.postgres_port} "
        f"dbname={settings.postgres_db} "
        f"user={settings.postgres_user} "
        f"password={settings.postgres_password.get_secret_value()}"
    )

    print(
        f"[verify] conectando a {settings.postgres_host}:{settings.postgres_port}"
        f"/{settings.postgres_db} como {settings.postgres_user}..."
    )

    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn, conn.cursor() as cur:
            cur.execute("SELECT version();")
            row = cur.fetchone()
            version = row[0] if row else "desconocida"
            print(f"[verify] conectado. PostgreSQL: {version.splitlines()[0]}")

            cur.execute(
                "SELECT extname, extversion FROM pg_extension "
                "WHERE extname = ANY(%s) ORDER BY extname;",
                (list(REQUIRED_EXTENSIONS),),
            )
            installed = dict(cur.fetchall())
    except Exception as exc:
        print(f"[verify] ERROR conectando a la base de datos: {exc}")
        return 1

    missing = [ext for ext in REQUIRED_EXTENSIONS if ext not in installed]

    print("[verify] extensiones detectadas:")
    for ext in REQUIRED_EXTENSIONS:
        if ext in installed:
            print(f"  OK   {ext} (v{installed[ext]})")
        else:
            print(f"  FALTA {ext}")

    if missing:
        print(f"[verify] FALLÓ: faltan extensiones {missing}")
        return 1

    print("[verify] todo correcto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
