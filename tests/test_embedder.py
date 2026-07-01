"""Tests del módulo de embeddings.

No tocan red: la API de OpenAI se sustituye por un fake y el conteo de tokens
se mockea donde interesa aislar el cálculo de coste.
"""

from __future__ import annotations

from typing import Any

import pytest

from cloud_data_docs.ingestion import embedder
from cloud_data_docs.ingestion.embedder import (
    EMBEDDING_DIM,
    embed_texts,
    estimate_cost,
)


def test_estimate_cost_returns_reasonable_numbers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con un conteo de tokens fijo, el coste sale del precio por 1M tokens."""
    # Mock del conteo: cada texto cuenta exactamente 1000 tokens.
    monkeypatch.setattr(embedder, "count_tokens", lambda _text: 1000)

    result = estimate_cost(["a", "b", "c"], model="text-embedding-3-small")

    assert result["total_tokens"] == 3000
    # 3000 tokens * $0.02 / 1M = $0.00006
    assert result["estimated_cost_usd"] == pytest.approx(3000 / 1_000_000 * 0.02)
    assert result["estimated_cost_usd"] > 0


def test_estimate_cost_unknown_model_raises() -> None:
    """Un modelo sin precio configurado falla de forma explícita."""
    with pytest.raises(ValueError, match="precio desconocido"):
        estimate_cost(["x"], model="modelo-inexistente")


class _FakeEmbeddingItem:
    """Imita un item de `response.data` de la API de embeddings."""

    def __init__(self, index: int, dim: int) -> None:
        self.index = index
        # Vector determinista: facilita aserciones sin depender de aleatoriedad.
        self.embedding = [float(index)] * dim


class _FakeResponse:
    def __init__(self, n: int, dim: int) -> None:
        self.data = [_FakeEmbeddingItem(i, dim) for i in range(n)]


class _FakeEmbeddings:
    def __init__(self, dim: int) -> None:
        self._dim = dim
        self.calls = 0

    def create(self, *, model: str, input: list[str]) -> _FakeResponse:
        self.calls += 1
        return _FakeResponse(len(input), self._dim)


class _FakeClient:
    def __init__(self, dim: int) -> None:
        self.embeddings = _FakeEmbeddings(dim)


def test_embed_texts_returns_correct_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """embed_texts devuelve un vector de 1536 dims por texto, en orden."""
    fake_client = _FakeClient(EMBEDDING_DIM)
    monkeypatch.setattr(embedder, "_get_client", lambda: fake_client)

    texts = [f"texto {i}" for i in range(5)]
    vectors = embed_texts(texts, batch_size=2)

    assert len(vectors) == len(texts)
    assert all(len(v) == EMBEDDING_DIM for v in vectors)
    # batch_size=2 sobre 5 textos => 3 llamadas (2+2+1).
    assert fake_client.embeddings.calls == 3
    # El orden se preserva: el primer item de cada batch arranca en index 0.
    assert vectors[0][0] == 0.0


def test_embed_texts_empty_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin textos no se llama a la API y se devuelve lista vacía."""

    def _boom() -> Any:
        raise AssertionError("no debería crearse cliente para input vacío")

    monkeypatch.setattr(embedder, "_get_client", _boom)
    assert embed_texts([]) == []
