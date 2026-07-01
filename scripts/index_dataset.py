"""CLI: chunking + embeddings + carga a pgvector del dataset de Snowflake.

Uso:
    uv run python scripts/index_dataset.py --dry-run   # estima, no gasta
    uv run python scripts/index_dataset.py --pilot      # indexa 5 docs (seed 42)
    uv run python scripts/index_dataset.py              # indexa los 48 docs
"""

from __future__ import annotations

import random
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cloud_data_docs.common.logging import configure_logging, logger
from cloud_data_docs.ingestion.indexer import IndexingResult, index_documents

# Mismo seed que el muestreo del scraping: pilotos reproducibles.
PILOT_SEED = 42
PILOT_COUNT = 5
DATASET_DIR = Path("data/processed/snowflake")

app = typer.Typer(add_completion=False, help="Indexador de chunks en pgvector")
console = Console()


def _discover_docs(pilot: bool) -> list[Path]:
    """Lista los `.md` del dataset. En modo piloto, muestrea 5 con seed fijo."""
    paths = sorted(DATASET_DIR.glob("*.md"))
    if not paths:
        raise FileNotFoundError(f"no hay .md en {DATASET_DIR}")
    if pilot:
        rng = random.Random(PILOT_SEED)
        return sorted(rng.sample(paths, min(PILOT_COUNT, len(paths))))
    return paths


def _render_result(result: IndexingResult, *, dry_run: bool) -> None:
    """Pinta el resumen del run con tablas rich."""
    title = "Resumen del indexado (DRY-RUN)" if dry_run else "Resumen del indexado"
    summary = Table(title=title)
    summary.add_column("Métrica", style="cyan")
    summary.add_column("Valor", justify="right")
    summary.add_row("Docs procesados", str(result.docs_processed))
    if dry_run:
        summary.add_row("Chunks que se crearían", str(result.chunks_skipped))
    else:
        summary.add_row("Chunks creados", str(result.chunks_created))
        summary.add_row("Chunks actualizados", str(result.chunks_updated))
        summary.add_row("Huérfanos borrados", str(result.chunks_deleted))
    summary.add_row("Tokens totales", str(result.total_tokens))
    cost_label = "Coste estimado ($)" if dry_run else "Coste real ($)"
    summary.add_row(cost_label, f"{result.total_cost_usd:.4f}")
    summary.add_row("Duración (s)", f"{result.duration_seconds:.1f}")
    console.print(summary)

    if result.chunks_per_section:
        dist = Table(title="Distribución de chunks por sección")
        dist.add_column("Sección", style="magenta")
        dist.add_column("Chunks", justify="right")
        for section, count in sorted(result.chunks_per_section.items()):
            dist.add_row(section, str(count))
        console.print(dist)

    if result.token_stats:
        stats = Table(title="Tokens por chunk")
        stats.add_column("Estadístico", style="green")
        stats.add_column("Valor", justify="right")
        stats.add_row("min", str(result.token_stats.get("min", "—")))
        stats.add_row("mediana", str(result.token_stats.get("median", "—")))
        stats.add_row("max", str(result.token_stats.get("max", "—")))
        console.print(stats)


@app.command()
def run(
    pilot: bool = typer.Option(
        False, "--pilot", help="Modo piloto: solo 5 documentos (seed 42)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Carga y estima coste, sin llamar a OpenAI ni DB."
    ),
) -> None:
    """Indexa los documentos Markdown en la tabla `chunks` de pgvector."""
    configure_logging()

    try:
        doc_paths = _discover_docs(pilot)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        raise typer.Exit(code=1) from exc

    logger.info(
        f"indexado: {len(doc_paths)} docs | pilot={pilot} | dry_run={dry_run}"
    )

    try:
        result = index_documents(doc_paths, dry_run=dry_run, confirm_cost=True)
    except Exception as exc:
        logger.error(f"indexado abortado: {exc}")
        raise typer.Exit(code=1) from exc

    _render_result(result, dry_run=dry_run)


if __name__ == "__main__":
    app()
