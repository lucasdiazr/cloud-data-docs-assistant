"""Tests mínimos del paquete ingestion.

Cubren intencionalidad básica:
- el extractor falla limpio con HTML vacío;
- el modelo serializa a JSON con los campos esperados;
- el clasificador de URLs filtra por las rutas objetivo (sin tocar red).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from cloud_data_docs.ingestion.extractors.trafilatura_extractor import (
    ExtractionError,
    _clean_markdown,
    _clean_title,
    _preprocess_snowflake_html,
    extract_clean_text,
)
from cloud_data_docs.ingestion.models import ScrapedDocument
from cloud_data_docs.ingestion.pipeline import _sample_balanced, url_to_slug
from cloud_data_docs.ingestion.scrapers.snowflake import SnowflakeScraper


def test_extractor_handles_empty_html() -> None:
    """HTML vacío debe levantar `ExtractionError`, no devolver basura."""
    with pytest.raises(ExtractionError):
        extract_clean_text("", "https://docs.snowflake.com/en/sql-reference/test")


def test_clean_markdown_strips_snowflake_boilerplate() -> None:
    """`_clean_markdown` quita anchor links `[¶](...)` y pilcrows sueltos."""
    raw = (
        "# Object identifiers[¶](https://docs.snowflake.com#object-identifiers)\n\n"
        "An identifier is...¶\n"
    )
    cleaned = _clean_markdown(raw)
    assert "¶" not in cleaned
    assert "[¶]" not in cleaned
    assert cleaned.startswith("# Object identifiers")


def test_clean_title_strips_pilcrow() -> None:
    """`_clean_title` quita pilcrow del título extraído por trafilatura."""
    assert _clean_title("SELECT¶") == "SELECT"
    assert _clean_title("  Identifiers ¶  ") == "Identifiers"


def test_preprocess_unwraps_snowflake_codeblock() -> None:
    """El wrapper de Snowflake se sustituye por un `<pre>` con el código dentro."""
    html = (
        "<html><body>"
        "<h2>Syntax</h2>"
        '<div class="codeblock-wrapper relative">'
        '<button class="codeblock-button">Copy</button>'
        "<pre><code>SELECT 1;\nFROM dual;</code></pre>"
        '<button class="codeblock-button">Expand</button>'
        "</div>"
        "</body></html>"
    )
    out = _preprocess_snowflake_html(html)
    soup = BeautifulSoup(out, "lxml")
    assert soup.find("div", class_="codeblock-wrapper") is None
    pres = soup.find_all("pre")
    assert len(pres) == 1
    assert "SELECT 1;" in pres[0].get_text()
    assert "FROM dual;" in pres[0].get_text()


def test_preprocess_passthrough_when_no_wrappers() -> None:
    """Si el HTML no contiene ningún `codeblock-wrapper`, se devuelve sin cambios."""
    html = "<html><body><p>hola</p></body></html>"
    assert _preprocess_snowflake_html(html) is html


def test_model_serializes_correctly() -> None:
    """`ScrapedDocument` se serializa a dict JSON-ready con los campos clave."""
    doc = ScrapedDocument(
        url="https://docs.snowflake.com/en/sql-reference/sql/select",  # type: ignore[arg-type]
        title="SELECT",
        section="sql-reference",
        scraped_at=datetime(2026, 5, 16, tzinfo=UTC),
        word_count=1234,
        status="success",
    )
    data = doc.model_dump(mode="json")
    assert data["section"] == "sql-reference"
    assert data["word_count"] == 1234
    assert data["status"] == "success"
    assert data["title"] == "SELECT"
    assert "scraped_at" in data and data["scraped_at"].startswith("2026-05-16")


def test_url_discovery_returns_filtered_paths(tmp_path: Path) -> None:
    """El clasificador interno deja pasar sql-reference y migrate y descarta el resto."""
    scraper = SnowflakeScraper(
        base_url="https://docs.snowflake.com",
        user_agent="test-agent",
        raw_dir=tmp_path,
        processed_dir=tmp_path,
    )
    assert (
        scraper._classify("https://docs.snowflake.com/en/sql-reference/sql/select")
        == "sql-reference"
    )
    assert (
        scraper._classify("https://docs.snowflake.com/en/migrations/guides/redshift")
        == "migrations"
    )
    assert scraper._classify("https://docs.snowflake.com/en/user-guide/intro") is None


def test_url_to_slug_strips_base_and_replaces_slashes() -> None:
    """Slug seguro: sin slashes, sin prefijo del dominio."""
    assert (
        url_to_slug("https://docs.snowflake.com/en/sql-reference/sql/select/")
        == "en__sql-reference__sql__select"
    )


def test_sample_balanced_respects_ratio() -> None:
    """Muestreo determinista: 60% sql-reference + 40% migrations."""
    candidates = [
        *[(f"https://docs.snowflake.com/en/sql-reference/x{i}", "sql-reference") for i in range(100)],
        *[(f"https://docs.snowflake.com/en/migrations/y{i}", "migrations") for i in range(100)],
    ]
    selected = _sample_balanced(candidates, target_count=10, seed=42)
    sql_n = sum(1 for _, sec in selected if sec == "sql-reference")
    mig_n = sum(1 for _, sec in selected if sec == "migrations")
    assert len(selected) == 10
    assert sql_n == 6
    assert mig_n == 4
