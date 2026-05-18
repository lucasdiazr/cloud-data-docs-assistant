"""Modelos Pydantic para el pipeline de ingesta.

`ScrapedDocument` representa un documento individual (resultado de intentar
scrapearlo) y `ScrapingResult` el resumen de un run completo.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

ScrapeStatus = Literal["success", "failed", "skipped"]
"""Estado por documento al finalizar el pipeline."""

DocSection = Literal["sql-reference", "migrations"]
"""Sección de Snowflake docs a la que pertenece un documento."""


def _utc_now() -> datetime:
    """Timestamp actual en UTC, usado como default para `scraped_at`."""
    return datetime.now(UTC)


class ScrapedDocument(BaseModel):
    """Resultado del intento de scrapear una URL concreta."""

    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    title: str | None = None
    section: DocSection
    html_raw_path: str | None = None
    markdown_path: str | None = None
    scraped_at: datetime = Field(default_factory=_utc_now)
    word_count: int = 0
    status: ScrapeStatus
    error_message: str | None = None


class ScrapingResult(BaseModel):
    """Resumen agregado de un run completo de scraping."""

    model_config = ConfigDict(extra="forbid")

    total_discovered: int
    total_downloaded: int
    total_failed: int
    total_skipped: int
    duration_seconds: float
    documents: list[ScrapedDocument] = Field(default_factory=list)
