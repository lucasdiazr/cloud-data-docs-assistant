"""Pipeline de indexado: Markdown -> chunks -> embeddings -> pgvector.

Orquesta los módulos `chunker` y `embedder` y persiste en la tabla `chunks`.
La inserción es idempotente vía `ON CONFLICT (doc_url, chunk_index) DO UPDATE`:
re-indexar un documento actualiza sus filas en lugar de duplicarlas.

El modo `dry_run` recorre carga + chunking + estimación de coste SIN llamar a
OpenAI ni escribir en la DB: sirve para ver cuántos chunks saldrían y cuánto
costaría antes de gastar nada.
"""

from __future__ import annotations

import statistics
import time
from collections import Counter
from pathlib import Path

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from cloud_data_docs.common.logging import logger
from cloud_data_docs.db.connection import get_connection
from cloud_data_docs.ingestion.chunker import (
    Chunk,
    FrontMatter,
    chunk_document,
    load_markdown_doc,
)
from cloud_data_docs.ingestion.embedder import (
    DEFAULT_EMBEDDING_MODEL,
    embed_texts,
    estimate_cost,
)

# Umbral de coste por encima del cual pedimos confirmación interactiva.
_COST_CONFIRM_THRESHOLD_USD = 0.10

_INSERT_SQL = """
INSERT INTO chunks (
    doc_url, doc_title, section, heading_path, chunk_index,
    content, embedding, token_count, metadata
)
VALUES (%s, %s, %s, %s, %s, %s, %s::vector, %s, %s)
ON CONFLICT (doc_url, chunk_index) DO UPDATE SET
    doc_title    = EXCLUDED.doc_title,
    section      = EXCLUDED.section,
    heading_path = EXCLUDED.heading_path,
    content      = EXCLUDED.content,
    embedding    = EXCLUDED.embedding,
    token_count  = EXCLUDED.token_count,
    metadata     = EXCLUDED.metadata
RETURNING (xmax = 0) AS inserted;
"""

# Borra chunks huérfanos de un doc: filas de un run anterior cuyo chunk_index
# quedó fuera de rango porque el doc ahora produce MENOS chunks (p.ej. tras
# limpiar el texto, un doc pasa de 6 a 4 chunks -> los índices 4 y 5 sobran).
# El ON CONFLICT actualiza 0..N-1 pero no toca esas filas viejas; esto sí.
_DELETE_ORPHANS_SQL = """
DELETE FROM chunks WHERE doc_url = %s AND chunk_index >= %s;
"""


class IndexingResult(BaseModel):
    """Métricas agregadas de un run de indexado."""

    model_config = ConfigDict(extra="forbid")

    docs_processed: int
    chunks_created: int
    chunks_updated: int
    chunks_skipped: int
    chunks_deleted: int = 0
    total_tokens: int
    total_cost_usd: float
    duration_seconds: float
    # Métricas auxiliares para el reporte del CLI.
    chunks_per_section: dict[str, int] = Field(default_factory=dict)
    token_stats: dict[str, int] = Field(default_factory=dict)


def _load_and_chunk(doc_paths: list[Path]) -> list[tuple[FrontMatter, Chunk]]:
    """Carga y chunkea cada doc; devuelve pares (frontmatter, chunk) aplanados."""
    pairs: list[tuple[FrontMatter, Chunk]] = []
    for path in doc_paths:
        frontmatter, body = load_markdown_doc(path)
        chunks = chunk_document(body, frontmatter)
        logger.info(f"{path.name}: {len(chunks)} chunks")
        for chunk in chunks:
            pairs.append((frontmatter, chunk))
    return pairs


def _vector_literal(embedding: list[float]) -> str:
    """Serializa un vector a literal pgvector ('[0.1,0.2,...]')."""
    return "[" + ",".join(str(x) for x in embedding) + "]"


def _token_stats(pairs: list[tuple[FrontMatter, Chunk]]) -> dict[str, int]:
    """Calcula min/max/mediana de token_count sobre todos los chunks."""
    if not pairs:
        return {}
    counts = [chunk.token_count for _, chunk in pairs]
    return {
        "min": min(counts),
        "max": max(counts),
        "median": int(statistics.median(counts)),
    }


def _section_distribution(pairs: list[tuple[FrontMatter, Chunk]]) -> dict[str, int]:
    """Cuenta chunks por sección (sql-reference vs migrations)."""
    return dict(Counter(fm.section for fm, _ in pairs))


def _confirm_cost(cost_usd: float) -> bool:
    """Pide confirmación interactiva si el coste supera el umbral.

    Devuelve True si se debe proceder, False si el usuario aborta. Si el coste
    está por debajo del umbral, no pregunta y devuelve True.
    """
    if cost_usd <= _COST_CONFIRM_THRESHOLD_USD:
        return True
    answer = input(
        f"\nEl indexado costará ~${cost_usd:.4f} (> ${_COST_CONFIRM_THRESHOLD_USD}). "
        f"¿Continuar? [y/N]: "
    )
    return answer.strip().lower() in {"y", "yes", "s", "si", "sí"}


def _insert_chunks(
    pairs: list[tuple[FrontMatter, Chunk]],
    embeddings: list[list[float]],
) -> tuple[int, int, int]:
    """Inserta/actualiza chunks y borra huérfanos. Devuelve (creados, actualizados, borrados).

    Todo ocurre en una única transacción: si algo falla, ni se insertan chunks
    ni se borran huérfanos (rollback atómico).
    """
    created = 0
    updated = 0
    deleted = 0
    # Nº de chunks generados por doc en ESTE run: define el rango válido de
    # chunk_index (0..count-1) para la limpieza de huérfanos.
    doc_chunk_counts = Counter(fm.url for fm, _ in pairs)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for (frontmatter, chunk), embedding in zip(pairs, embeddings, strict=True):
                metadata = Jsonb(
                    {
                        "source": "snowflake",
                        "doc_word_count": frontmatter.word_count,
                        "scraped_at": frontmatter.scraped_at.isoformat(),
                    }
                )
                cur.execute(
                    _INSERT_SQL,
                    (
                        frontmatter.url,
                        frontmatter.title,
                        frontmatter.section,
                        chunk.heading_path,
                        chunk.chunk_index,
                        chunk.content,
                        _vector_literal(embedding),
                        chunk.token_count,
                        metadata,
                    ),
                )
                row = cur.fetchone()
                if row is not None and row[0]:
                    created += 1
                else:
                    updated += 1

            # Limpieza de huérfanos: por cada doc, borra las filas cuyo
            # chunk_index cae fuera del nuevo rango [0, count).
            for doc_url, count in doc_chunk_counts.items():
                cur.execute(_DELETE_ORPHANS_SQL, (doc_url, count))
                deleted += cur.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return created, updated, deleted


def index_documents(
    doc_paths: list[Path],
    *,
    dry_run: bool = False,
    confirm_cost: bool = True,
) -> IndexingResult:
    """Indexa una lista de documentos Markdown en la tabla `chunks`.

    Args:
        doc_paths: Rutas a los `.md` a indexar.
        dry_run: Si True, carga + chunkea + estima coste pero NO llama a OpenAI
            ni escribe en la DB.
        confirm_cost: Si True y el coste estimado supera el umbral, pide
            confirmación interactiva antes de embeber.

    Returns:
        `IndexingResult` con las métricas del run.
    """
    start = time.monotonic()

    logger.info(f"cargando y chunkeando {len(doc_paths)} documento(s)")
    pairs = _load_and_chunk(doc_paths)
    contents = [chunk.content for _, chunk in pairs]

    cost = estimate_cost(contents, model=DEFAULT_EMBEDDING_MODEL)
    total_tokens = int(cost["total_tokens"])
    total_cost_usd = float(cost["estimated_cost_usd"])
    token_stats = _token_stats(pairs)
    section_dist = _section_distribution(pairs)

    logger.info(
        f"{len(pairs)} chunks | {total_tokens} tokens | "
        f"coste estimado ${total_cost_usd:.4f}"
    )

    if dry_run:
        logger.info("dry-run: no se llama a OpenAI ni se escribe en la DB")
        return IndexingResult(
            docs_processed=len(doc_paths),
            chunks_created=0,
            chunks_updated=0,
            chunks_skipped=len(pairs),
            total_tokens=total_tokens,
            total_cost_usd=total_cost_usd,
            duration_seconds=time.monotonic() - start,
            chunks_per_section=section_dist,
            token_stats=token_stats,
        )

    if confirm_cost and not _confirm_cost(total_cost_usd):
        logger.warning("indexado abortado por el usuario en la confirmación de coste")
        return IndexingResult(
            docs_processed=len(doc_paths),
            chunks_created=0,
            chunks_updated=0,
            chunks_skipped=len(pairs),
            total_tokens=total_tokens,
            total_cost_usd=0.0,
            duration_seconds=time.monotonic() - start,
            chunks_per_section=section_dist,
            token_stats=token_stats,
        )

    logger.info("generando embeddings con OpenAI")
    embeddings = embed_texts(contents, model=DEFAULT_EMBEDDING_MODEL)

    logger.info("insertando chunks en pgvector (ON CONFLICT DO UPDATE)")
    created, updated, deleted = _insert_chunks(pairs, embeddings)

    duration = time.monotonic() - start
    logger.info(
        f"indexado completo: {created} creados, {updated} actualizados, "
        f"{deleted} huérfanos borrados en {duration:.1f}s"
    )

    return IndexingResult(
        docs_processed=len(doc_paths),
        chunks_created=created,
        chunks_updated=updated,
        chunks_skipped=0,
        chunks_deleted=deleted,
        total_tokens=total_tokens,
        total_cost_usd=total_cost_usd,
        duration_seconds=duration,
        chunks_per_section=section_dist,
        token_stats=token_stats,
    )


__all__ = ["IndexingResult", "index_documents"]
