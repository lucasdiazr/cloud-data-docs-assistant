"""Re-extrae los `.md` a partir del HTML crudo, sin tocar la red.

Útil cuando el extractor cambia y queremos regenerar el dataset sin
re-pagar el coste de descarga. Lee el manifest actual, recorre todos los
documentos con `html_raw_path` existente y reescribe el `.md` (preservando
el `scraped_at` original). Actualiza el manifest al final.

Uso:
    uv run python scripts/reprocess_snowflake.py
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from cloud_data_docs.common.logging import configure_logging, logger
from cloud_data_docs.ingestion.extractors.trafilatura_extractor import (
    ExtractionError,
    extract_clean_text,
)
from cloud_data_docs.ingestion.models import ScrapedDocument, ScrapingResult
from cloud_data_docs.ingestion.pipeline import (
    DEFAULT_PROCESSED_DIR,
    MANIFEST_NAME,
    _build_frontmatter,
    _cast_section,
    url_to_slug,
)


def main() -> int:
    """Recorre el manifest, re-extrae cada `.md` desde el HTML local y reescribe."""
    configure_logging()
    start = time.monotonic()

    manifest_path = DEFAULT_PROCESSED_DIR / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    rebuilt: list[ScrapedDocument] = []
    n_ok = n_fail = n_preserved = 0

    for d in manifest["documents"]:
        html_path_str = d.get("html_raw_path")
        html_path = Path(html_path_str) if html_path_str else None
        if html_path is None or not html_path.exists():
            # No hay HTML crudo: preservamos el registro tal cual (sin reprocesar).
            rebuilt.append(ScrapedDocument(**d))
            n_preserved += 1
            continue

        original_scraped_at = datetime.fromisoformat(d["scraped_at"])
        section = _cast_section(d["section"])

        try:
            html = html_path.read_text(encoding="utf-8")
            extracted = extract_clean_text(html, d["url"])
        except ExtractionError as exc:
            logger.warning(f"reproceso fallido: {d['url']}: {exc}")
            rebuilt.append(
                ScrapedDocument(
                    url=d["url"],
                    section=section,
                    html_raw_path=str(html_path),
                    scraped_at=original_scraped_at,
                    status="failed",
                    error_message=f"ExtractionError: {exc}",
                )
            )
            n_fail += 1
            continue

        # Si el manifest no tenía markdown_path (porque originalmente falló
        # la extracción y ahora sí pasa), lo derivamos a partir del slug.
        md_path_str = d.get("markdown_path") or str(
            DEFAULT_PROCESSED_DIR / f"{url_to_slug(d['url'])}.md"
        )

        new_doc = ScrapedDocument(
            url=d["url"],
            title=extracted["title"],
            section=section,
            html_raw_path=str(html_path),
            markdown_path=md_path_str,
            scraped_at=original_scraped_at,
            word_count=extracted["word_count"],
            status="success",
        )
        Path(md_path_str).write_text(
            _build_frontmatter(new_doc) + extracted["markdown_body"] + "\n",
            encoding="utf-8",
        )
        rebuilt.append(new_doc)
        n_ok += 1

    result = ScrapingResult(
        total_discovered=manifest["total_discovered"],
        total_downloaded=n_ok,
        total_failed=n_fail,
        total_skipped=0,
        duration_seconds=time.monotonic() - start,
        documents=rebuilt,
    )
    manifest_path.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    logger.info(
        f"reproceso completo: {n_ok} sobrescritos | "
        f"{n_fail} fallos | {n_preserved} preservados (sin HTML local)"
    )
    print(f"sobrescribed_md_count={n_ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
