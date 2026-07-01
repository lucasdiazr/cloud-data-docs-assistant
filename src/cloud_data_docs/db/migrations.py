"""Migraciones de esquema para la base vectorial.

La migración es idempotente: todo es `CREATE ... IF NOT EXISTS`, por lo que
`run_migrations` puede ejecutarse cuantas veces se quiera sin efectos
secundarios. La extensión `vector` (pgvector) se asume ya instalada por
`init-db.sql` en el primer arranque del contenedor; aquí solo creamos la
tabla y sus índices.
"""

from __future__ import annotations

import psycopg

from cloud_data_docs.common.logging import logger

# DDL de la tabla de chunks. El embedding es vector(1536) porque usamos
# text-embedding-3-small. UNIQUE(doc_url, chunk_index) da la idempotencia del
# indexado: re-indexar un doc actualiza (ON CONFLICT) en vez de duplicar.
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS chunks (
    id              BIGSERIAL PRIMARY KEY,
    doc_url         TEXT NOT NULL,
    doc_title       TEXT NOT NULL,
    section         TEXT NOT NULL,
    heading_path    TEXT,
    chunk_index     INT NOT NULL,
    content         TEXT NOT NULL,
    embedding       vector(1536) NOT NULL,
    token_count     INT NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (doc_url, chunk_index)
);
"""

# Índice HNSW con operador coseno: alinea con cómo recuperaremos (similitud
# coseno sobre embeddings normalizados de OpenAI).
_CREATE_HNSW_INDEX = """
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);
"""

# Índices auxiliares para filtrado relacional (por sección y por documento).
_CREATE_SECTION_INDEX = """
CREATE INDEX IF NOT EXISTS chunks_section_idx ON chunks(section);
"""

_CREATE_DOC_URL_INDEX = """
CREATE INDEX IF NOT EXISTS chunks_doc_url_idx ON chunks(doc_url);
"""

_MIGRATION_STEPS = (
    ("tabla chunks", _CREATE_TABLE),
    ("índice HNSW", _CREATE_HNSW_INDEX),
    ("índice section", _CREATE_SECTION_INDEX),
    ("índice doc_url", _CREATE_DOC_URL_INDEX),
)


def run_migrations(conn: psycopg.Connection) -> None:
    """Aplica el esquema de la tabla `chunks` y sus índices (idempotente).

    No hace commit: la transacción la confirma el llamador. Así el script de
    ejecución decide la política de commit/rollback.

    Args:
        conn: Conexión psycopg síncrona ya abierta.
    """
    with conn.cursor() as cur:
        for name, ddl in _MIGRATION_STEPS:
            logger.info(f"aplicando migración: {name}")
            cur.execute(ddl)
    logger.info("migraciones aplicadas (pendiente commit del llamador)")


__all__ = ["run_migrations"]
