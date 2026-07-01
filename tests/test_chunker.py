"""Tests del módulo de chunking.

No tocan red ni DB: trabajan sobre Markdown sintético en memoria salvo el test
de frontmatter, que escribe un `.md` temporal con `tmp_path`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cloud_data_docs.ingestion.chunker import (
    FrontMatter,
    chunk_document,
    count_tokens,
    load_markdown_doc,
)

_FRONTMATTER_DOC = """\
---
url: "https://docs.snowflake.com/en/sql-reference/sql/select"
title: "SELECT"
section: sql-reference
scraped_at: 2026-05-18T12:50:51.556429+00:00
word_count: 123
---

# SELECT

Cuerpo del documento.
"""


@pytest.fixture
def frontmatter() -> FrontMatter:
    """FrontMatter mínimo reutilizable en los tests de chunking."""
    return FrontMatter(
        url="https://docs.snowflake.com/en/sql-reference/sql/select",
        title="SELECT",
        section="sql-reference",
        scraped_at="2026-05-18T12:50:51.556429+00:00",  # type: ignore[arg-type]
        word_count=123,
    )


def test_load_markdown_extracts_frontmatter(tmp_path: Path) -> None:
    """El frontmatter YAML se parsea a FrontMatter y el body queda limpio."""
    path = tmp_path / "select.md"
    path.write_text(_FRONTMATTER_DOC, encoding="utf-8")

    front, body = load_markdown_doc(path)

    assert front.url == "https://docs.snowflake.com/en/sql-reference/sql/select"
    assert front.title == "SELECT"
    assert front.section == "sql-reference"
    assert front.word_count == 123
    # El body no debe arrastrar el bloque de frontmatter.
    assert "url:" not in body
    assert body.startswith("# SELECT")


def test_chunking_preserves_heading_path(frontmatter: FrontMatter) -> None:
    """El heading_path refleja la jerarquía real (h1 > h2 > h3), sin '>>>'."""
    # Cada sección debe superar min_chunk_tokens para sobrevivir como chunk
    # propio (si fueran diminutas, el merge las colapsaría — eso se prueba
    # aparte en test_small_chunks_are_merged).
    filler = "Texto explicativo con suficiente longitud para el umbral. " * 4
    body = (
        f"# Description\n\n{filler}\n\n"
        f"## Syntax\n\n{filler}\n\n"
        f"### Parameters\n\n{filler}\n"
    )

    chunks = chunk_document(body, frontmatter)

    paths = {c.heading_path for c in chunks}
    assert "Description" in paths
    assert "Description > Syntax" in paths
    assert "Description > Syntax > Parameters" in paths
    # Ningún heading_path degenerado del tipo '> > >'.
    for c in chunks:
        assert c.heading_path is None or ">" not in c.heading_path.replace(" > ", "")


def test_small_chunks_are_merged(frontmatter: FrontMatter) -> None:
    """Una sección diminuta (< min_chunk_tokens) se funde con su vecina."""
    body = (
        "# Overview\n\n"
        + "Esta es una sección con suficiente contenido para superar el umbral "
        "mínimo de tokens y existir como chunk propio. " * 4
        + "\n\n## Note\n\nok\n"  # sección diminuta: debe mergearse
    )

    # Con merge: el "## Note\n\nok" (muy corto) no debe sobrevivir como chunk solo.
    chunks = chunk_document(body, frontmatter, min_chunk_tokens=50)

    assert all(c.token_count >= 50 for c in chunks), (
        f"hay chunks por debajo del umbral: "
        f"{[c.token_count for c in chunks]}"
    )
    # El contenido diminuto sigue presente, fusionado en algún chunk.
    assert any("ok" in c.content for c in chunks)


def test_oversized_sections_are_split(frontmatter: FrontMatter) -> None:
    """Una sección que supera target_tokens se sub-parte en varios chunks."""
    # Párrafos repetidos para superar holgadamente el target de tokens.
    big_paragraph = (
        "Snowflake procesa las consultas distribuyendo el trabajo entre los "
        "nodos del warehouse virtual, optimizando el plan y materializando "
        "resultados intermedios cuando conviene. "
    )
    body = "# Big Section\n\n" + ("\n\n".join([big_paragraph] * 60))

    target = 200
    chunks = chunk_document(body, frontmatter, target_tokens=target, overlap_tokens=40)

    assert len(chunks) > 1, "una sección enorme debería producir varios chunks"
    # Ningún chunk se dispara muy por encima del target (con holgura por overlap).
    assert all(c.token_count <= target * 1.5 for c in chunks), (
        f"chunks demasiado grandes: {[c.token_count for c in chunks]}"
    )
    # chunk_index consecutivo desde 0.
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_count_tokens_is_positive() -> None:
    """count_tokens devuelve un entero positivo coherente para texto real."""
    assert count_tokens("CREATE TABLE foo (id INT);") > 0
    assert count_tokens("") == 0
