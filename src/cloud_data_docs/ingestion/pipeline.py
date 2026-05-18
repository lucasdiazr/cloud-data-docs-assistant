"""Pipeline asíncrono de scraping Snowflake.

Orquesta: descubrimiento (sitemap) → muestreo determinista → descarga →
extracción a Markdown → persistencia (HTML crudo + Markdown con frontmatter)
→ manifest.json. Idempotente: si el `.md` destino ya existe, se considera
`skipped` y no se re-descarga.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

from cloud_data_docs.common.logging import logger
from cloud_data_docs.ingestion.extractors.trafilatura_extractor import ExtractionError
from cloud_data_docs.ingestion.models import (
    DocSection,
    ScrapedDocument,
    ScrapingResult,
)
from cloud_data_docs.ingestion.scrapers.snowflake import SnowflakeScraper

USER_AGENT = (
    "cloud-data-docs-assistant/0.1 "
    "(educational; github.com/lucasdiazr)"
)
"""User-Agent declarado al servidor (educativo, identificable)."""

BASE_URL = "https://docs.snowflake.com"
DEFAULT_RAW_DIR = Path("data/raw/snowflake")
DEFAULT_PROCESSED_DIR = Path("data/processed/snowflake")
MANIFEST_NAME = "manifest.json"

SQL_REFERENCE_RATIO = 0.6
"""Proporción de URLs de /en/sql-reference/ en el muestreo final."""

RANDOM_SEED = 42
"""Seed fija para que el muestreo sea reproducible."""

FAIL_RATE_THRESHOLD = 0.30
"""Si > 30% de las URLs intentadas fallan, paramos y reportamos."""


class ScrapingAbortedError(RuntimeError):
    """Se levanta si una invariante crítica del run no se cumple."""


def url_to_slug(url: str, base_url: str = BASE_URL) -> str:
    """Convierte una URL en un nombre de archivo seguro (sin slashes).

    `https://docs.snowflake.com/en/sql-reference/sql/select`
        → `en__sql-reference__sql__select`
    """
    prefix = base_url.rstrip("/") + "/"
    return url.replace(prefix, "").rstrip("/").replace("/", "__")


def _build_frontmatter(doc: ScrapedDocument) -> str:
    """Construye un bloque YAML frontmatter para el archivo Markdown.

    Se serializa a mano (sin PyYAML) porque el contenido es trivial y
    así evitamos una dependencia extra.
    """
    safe_title = (doc.title or "").replace('"', "'")
    lines = [
        "---",
        f'url: "{doc.url}"',
        f'title: "{safe_title}"',
        f"section: {doc.section}",
        f"scraped_at: {doc.scraped_at.isoformat()}",
        f"word_count: {doc.word_count}",
        "---",
        "",
        "",
    ]
    return "\n".join(lines)


def _sample_balanced(
    candidates: list[tuple[str, str]],
    target_count: int,
    sql_ratio: float = SQL_REFERENCE_RATIO,
    seed: int = RANDOM_SEED,
) -> list[tuple[str, str]]:
    """Muestreo determinista 60% sql-reference + 40% migrate.

    Si una de las secciones tiene menos URLs disponibles que su cupo, se
    rellena con la otra.
    """
    sql_ref = [u for u in candidates if u[1] == "sql-reference"]
    migrations = [u for u in candidates if u[1] == "migrations"]
    rng = random.Random(seed)
    rng.shuffle(sql_ref)
    rng.shuffle(migrations)

    n_sql = min(round(target_count * sql_ratio), len(sql_ref))
    n_mig = min(target_count - n_sql, len(migrations))
    # Compensación si una sección no llega
    deficit = target_count - n_sql - n_mig
    if deficit > 0:
        extra_pool = sql_ref[n_sql:] if len(sql_ref) > n_sql else migrations[n_mig:]
        selected = sql_ref[:n_sql] + migrations[:n_mig] + extra_pool[:deficit]
    else:
        selected = sql_ref[:n_sql] + migrations[:n_mig]

    rng.shuffle(selected)
    return selected


async def run_scraping(
    target_count: int,
    *,
    dry_run: bool = False,
    raw_dir: Path = DEFAULT_RAW_DIR,
    processed_dir: Path = DEFAULT_PROCESSED_DIR,
) -> ScrapingResult:
    """Ejecuta el pipeline end-to-end y devuelve el resumen tipado.

    Args:
        target_count: Número objetivo de documentos a descargar.
        dry_run: Si True, solo descubre URLs (no descarga).
        raw_dir: Carpeta donde persistir HTML crudo.
        processed_dir: Carpeta donde persistir Markdown y manifest.json.
    """
    start = time.monotonic()
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    documents: list[ScrapedDocument] = []
    total_downloaded = 0
    total_failed = 0
    total_skipped = 0
    total_discovered = 0

    async with SnowflakeScraper(
        base_url=BASE_URL,
        user_agent=USER_AGENT,
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        rate_per_second=5.0,
        concurrency=5,
    ) as scraper:
        candidates = await scraper.discover_urls()
        total_discovered = len(candidates)

        if total_discovered == 0:
            raise ScrapingAbortedError(
                "sitemap no devolvió URLs en las secciones objetivo; revisar SITEMAP_URL"
            )

        if dry_run:
            return ScrapingResult(
                total_discovered=total_discovered,
                total_downloaded=0,
                total_failed=0,
                total_skipped=0,
                duration_seconds=time.monotonic() - start,
                documents=[],
            )

        selected = _sample_balanced(candidates, target_count)
        logger.info(f"seleccionadas {len(selected)} URLs (target={target_count})")

        # Verificar robots.txt antes de descargar
        forbidden = [u for (u, _) in selected if not scraper.can_fetch(u)]
        if forbidden:
            logger.error(
                f"robots.txt prohíbe scrapear {len(forbidden)} URLs. Ejemplos:"
            )
            for u in forbidden[:3]:
                logger.error(f"  - {u}")
            raise ScrapingAbortedError("robots.txt prohíbe parte del scraping")

        for idx, (url, section) in enumerate(selected, start=1):
            slug = url_to_slug(url)
            html_path = raw_dir / f"{slug}.html"
            md_path = processed_dir / f"{slug}.md"

            if md_path.exists():
                logger.info(f"[{idx}/{len(selected)}] skip (ya existe): {url}")
                total_skipped += 1
                documents.append(
                    ScrapedDocument(
                        url=url,  # type: ignore[arg-type]
                        section=_cast_section(section),
                        html_raw_path=str(html_path) if html_path.exists() else None,
                        markdown_path=str(md_path),
                        word_count=0,
                        status="skipped",
                    )
                )
                continue

            logger.info(f"[{idx}/{len(selected)}] descargando: {url}")
            try:
                html = await scraper.download(url)
                scraper.save_raw_html(slug, html)
                extracted = await scraper.extract(html, url)
            except ExtractionError as exc:
                logger.warning(f"extracción fallida: {url}: {exc}")
                documents.append(
                    ScrapedDocument(
                        url=url,  # type: ignore[arg-type]
                        section=_cast_section(section),
                        html_raw_path=str(html_path) if html_path.exists() else None,
                        status="failed",
                        error_message=f"ExtractionError: {exc}",
                    )
                )
                total_failed += 1
                continue
            except Exception as exc:
                logger.error(f"error descargando {url}: {exc}")
                documents.append(
                    ScrapedDocument(
                        url=url,  # type: ignore[arg-type]
                        section=_cast_section(section),
                        status="failed",
                        error_message=f"{type(exc).__name__}: {exc}",
                    )
                )
                total_failed += 1
                continue

            doc = ScrapedDocument(
                url=url,  # type: ignore[arg-type]
                title=extracted["title"],
                section=_cast_section(section),
                html_raw_path=str(html_path),
                markdown_path=str(md_path),
                word_count=extracted["word_count"],
                status="success",
            )
            scraper.save_markdown(slug, _build_frontmatter(doc) + extracted["markdown_body"] + "\n")
            documents.append(doc)
            total_downloaded += 1

    result = ScrapingResult(
        total_discovered=total_discovered,
        total_downloaded=total_downloaded,
        total_failed=total_failed,
        total_skipped=total_skipped,
        duration_seconds=time.monotonic() - start,
        documents=documents,
    )

    manifest_path = processed_dir / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(f"manifest escrito: {manifest_path}")

    attempted = total_downloaded + total_failed
    if attempted > 0:
        fail_rate = total_failed / attempted
        if fail_rate > FAIL_RATE_THRESHOLD:
            raise ScrapingAbortedError(
                f"tasa de fallos {fail_rate:.0%} > {FAIL_RATE_THRESHOLD:.0%}; revisar"
            )

    return result


def _cast_section(section: str) -> DocSection:
    """Cast estrecho de `str` a `DocSection` para satisfacer al tipador."""
    if section not in ("sql-reference", "migrations"):
        raise ValueError(f"sección inesperada: {section}")
    return section  # type: ignore[return-value]
