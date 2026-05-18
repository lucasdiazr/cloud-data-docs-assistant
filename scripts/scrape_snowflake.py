"""CLI: scrapeo del dataset piloto/completo de docs.snowflake.com.

Uso:
    uv run python scripts/scrape_snowflake.py --dry-run
    uv run python scripts/scrape_snowflake.py --pilot
    uv run python scripts/scrape_snowflake.py --target-count 50
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from cloud_data_docs.common.logging import configure_logging, logger
from cloud_data_docs.ingestion.models import ScrapingResult
from cloud_data_docs.ingestion.pipeline import run_scraping

PILOT_COUNT = 5
DEFAULT_TARGET = 50

app = typer.Typer(add_completion=False, help="Scraper de docs.snowflake.com")
console = Console()


def _render_summary(result: ScrapingResult) -> None:
    summary = Table(title="Resumen del run")
    summary.add_column("Métrica", style="cyan")
    summary.add_column("Valor", justify="right")
    summary.add_row("URLs descubiertas (sitemap, filtradas)", str(result.total_discovered))
    summary.add_row("Descargadas con éxito", str(result.total_downloaded))
    summary.add_row("Saltadas (ya existían)", str(result.total_skipped))
    summary.add_row("Fallidas", str(result.total_failed))
    summary.add_row("Duración (s)", f"{result.duration_seconds:.1f}")
    console.print(summary)


def _render_documents(result: ScrapingResult) -> None:
    if not result.documents:
        return
    table = Table(title="Documentos del run")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Sección", style="magenta")
    table.add_column("Status")
    table.add_column("Words", justify="right")
    table.add_column("Title", overflow="fold")
    table.add_column("URL", overflow="fold")
    for i, doc in enumerate(result.documents, 1):
        status_style = {
            "success": "[green]success[/green]",
            "failed": "[red]failed[/red]",
            "skipped": "[yellow]skipped[/yellow]",
        }.get(doc.status, doc.status)
        table.add_row(
            str(i),
            doc.section,
            status_style,
            str(doc.word_count),
            (doc.title or "—")[:60],
            str(doc.url),
        )
    console.print(table)


@app.command()
def run(
    target_count: int = typer.Option(
        DEFAULT_TARGET, "--target-count", help="Número objetivo de documentos."
    ),
    pilot: bool = typer.Option(
        False, "--pilot", help="Modo piloto: solo 5 documentos."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Solo descubre URLs, no descarga."
    ),
) -> None:
    """Ejecuta el pipeline de scraping."""
    configure_logging()
    effective_target = PILOT_COUNT if pilot else target_count
    logger.info(
        f"iniciando scraping: target={effective_target}, dry_run={dry_run}"
    )

    try:
        result = asyncio.run(run_scraping(target_count=effective_target, dry_run=dry_run))
    except Exception as exc:
        logger.error(f"pipeline abortado: {exc}")
        raise typer.Exit(code=1) from exc

    _render_summary(result)
    if not dry_run:
        _render_documents(result)


if __name__ == "__main__":
    app()
