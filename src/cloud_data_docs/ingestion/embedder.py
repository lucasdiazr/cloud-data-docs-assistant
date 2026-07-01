"""Generación de embeddings con la API de OpenAI.

Modelo por defecto: text-embedding-3-small (1536 dims). El batching reduce el
número de round-trips (OpenAI acepta hasta 2048 inputs por llamada; usamos 100
como tamaño cómodo). Los reintentos con tenacity absorben rate limits y cortes
de red transitorios.
"""

from __future__ import annotations

from openai import APIConnectionError, OpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from tqdm import tqdm

from cloud_data_docs.common.config import get_settings
from cloud_data_docs.common.logging import logger
from cloud_data_docs.ingestion.chunker import count_tokens

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

# Precio público de text-embedding-3-small: $0.02 por 1M de tokens.
_PRICE_PER_1M_TOKENS: dict[str, float] = {
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
}

# Umbral a partir del cual mostramos barra de progreso.
_PROGRESS_THRESHOLD = 50

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Devuelve un cliente OpenAI (lazy, cacheado a nivel de módulo).

    Aislado en una función para poder sustituirlo por un fake en los tests sin
    tocar red.
    """
    global _client
    if _client is None:
        api_key = get_settings().openai_api_key.get_secret_value()
        _client = OpenAI(api_key=api_key)
    return _client


def estimate_cost(
    texts: list[str],
    model: str = DEFAULT_EMBEDDING_MODEL,
) -> dict[str, float | int]:
    """Estima tokens y coste en USD ANTES de llamar a la API.

    Cuenta tokens localmente con tiktoken (cl100k_base), sin coste ni red.

    Args:
        texts: Textos a embeber.
        model: Modelo de embeddings (define el precio por token).

    Returns:
        Dict con `total_tokens` (int) y `estimated_cost_usd` (float).
    """
    total_tokens = sum(count_tokens(text) for text in texts)
    price = _PRICE_PER_1M_TOKENS.get(model)
    if price is None:
        raise ValueError(f"precio desconocido para el modelo {model!r}")
    estimated_cost_usd = total_tokens / 1_000_000 * price
    return {
        "total_tokens": total_tokens,
        "estimated_cost_usd": estimated_cost_usd,
    }


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
    reraise=True,
)
def _embed_batch(batch: list[str], model: str) -> list[list[float]]:
    """Embebe un único batch con reintento exponencial ante errores transitorios."""
    client = _get_client()
    response = client.embeddings.create(model=model, input=batch)
    # Ordenar por índice asegura el mismo orden que la entrada, sin depender de
    # que la API lo garantice implícitamente.
    ordered = sorted(response.data, key=lambda item: item.index)
    return [item.embedding for item in ordered]


def embed_texts(
    texts: list[str],
    model: str = DEFAULT_EMBEDDING_MODEL,
    batch_size: int = 100,
) -> list[list[float]]:
    """Genera embeddings para `texts`, en el mismo orden que la entrada.

    Args:
        texts: Lista de textos a embeber.
        model: Modelo de embeddings de OpenAI.
        batch_size: Nº de textos por llamada a la API (máx. cómodo 100).

    Returns:
        Lista de vectores (uno por texto), preservando el orden de entrada.
    """
    if not texts:
        return []

    batches = [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]
    show_progress = len(texts) > _PROGRESS_THRESHOLD
    logger.info(
        f"embebiendo {len(texts)} textos en {len(batches)} batch(es) "
        f"de hasta {batch_size} con {model}"
    )

    embeddings: list[list[float]] = []
    iterator = tqdm(batches, desc="embeddings", unit="batch", disable=not show_progress)
    for batch in iterator:
        embeddings.extend(_embed_batch(batch, model))

    return embeddings


__all__ = [
    "DEFAULT_EMBEDDING_MODEL",
    "EMBEDDING_DIM",
    "embed_texts",
    "estimate_cost",
]
