"""Genera `docs/dataset-report.md` a partir del manifest del scrape.

Cálculo de métricas (incluye porcentaje de docs con headings vacíos: un
heading `##` seguido por otro `##` sin contenido textual entre medias).

Uso:
    uv run python scripts/build_dataset_report.py
"""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

MANIFEST = Path("data/processed/snowflake/manifest.json")
REPORT = Path("docs/dataset-report.md")

EMPTY_HEADING_THRESHOLD = 10.0
"""Porcentaje por encima del cual el reporte marca el dataset como problemático."""


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5 :]
    return text


def _empty_heading_titles(md_body: str) -> list[str]:
    """Devuelve los títulos de los headings vacíos (definición refinada).

    Un heading se considera vacío si:
      1. No hay contenido textual entre él y el siguiente heading, y
      2. El siguiente heading es del **mismo nivel o superior**.

    La condición (2) descarta los falsos positivos por estructura
    jerárquica (un `## Padre` que arranca con un `### Hijo` sin texto
    propio: el contenido sigue presente, sólo vive en las sub-secciones).
    """
    lines = md_body.split("\n")
    headings: list[tuple[int, int]] = []
    for i, ln in enumerate(lines):
        match = re.match(r"^(#{2,})\s+\S", ln)
        if match:
            headings.append((i, len(match.group(1))))

    empties: list[str] = []
    for i, (idx, level) in enumerate(headings[:-1]):
        next_idx, next_level = headings[i + 1]
        between = lines[idx + 1 : next_idx]
        if all(not ln.strip() for ln in between) and next_level <= level:
            empties.append(lines[idx].lstrip("#").strip())
    return empties


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    docs = manifest["documents"]
    success = [d for d in docs if d["status"] == "success"]
    skipped = [d for d in docs if d["status"] == "skipped"]
    failed = [d for d in docs if d["status"] == "failed"]

    rows: list[tuple[str, int, str, str]] = []
    for d in success:
        rows.append((d["url"], d["word_count"], d["section"], d.get("title") or ""))
    for d in skipped:
        path = Path(d["markdown_path"])
        fm = path.read_text()
        m_wc = re.search(r"^word_count:\s*(\d+)", fm, re.MULTILINE)
        m_tit = re.search(r'^title:\s*"([^"]*)"', fm, re.MULTILINE)
        if m_wc:
            rows.append(
                (
                    d["url"],
                    int(m_wc.group(1)),
                    d["section"],
                    m_tit.group(1) if m_tit else "",
                )
            )

    wcs = [r[1] for r in rows]
    by_section_success = {
        "sql-reference": sum(1 for r in rows if r[2] == "sql-reference"),
        "migrations": sum(1 for r in rows if r[2] == "migrations"),
    }

    files_with_empty: list[tuple[str, list[str]]] = []
    empty_title_counter: dict[str, int] = {}
    for d in success + skipped:
        path = Path(d["markdown_path"])
        body = _strip_frontmatter(path.read_text())
        titles = _empty_heading_titles(body)
        if titles:
            files_with_empty.append((path.name, titles))
            for t in titles:
                empty_title_counter[t] = empty_title_counter.get(t, 0) + 1

    total_docs_with_md = len(rows)
    empty_pct = len(files_with_empty) / total_docs_with_md * 100 if total_docs_with_md else 0.0
    top_titles = sorted(empty_title_counter.items(), key=lambda x: -x[1])[:10]

    breach = empty_pct > EMPTY_HEADING_THRESHOLD
    severity_block = (
        f"> [!CAUTION]\n"
        f"> **{empty_pct:.1f}%** de los documentos contienen al menos un heading vacío "
        f"(`## X` seguido inmediatamente de otro `##` sin contenido entre medias). "
        f"El umbral aceptado era ≤ {EMPTY_HEADING_THRESHOLD:.0f}%. "
        f"**Calidad del dataset en revisión — no commitear hasta tomar una decisión.**"
        if breach
        else f"> [!NOTE]\n"
        f"> **{empty_pct:.1f}%** de los documentos contienen al menos un heading vacío (umbral ≤ {EMPTY_HEADING_THRESHOLD:.0f}%)."
    )

    lines: list[str] = []
    lines.append("# Dataset report — scrape de docs.snowflake.com")
    lines.append("")
    lines.append(
        "Resumen del primer dataset piloto descargado en local desde "
        "`docs.snowflake.com`. Generado automáticamente por "
        "`scripts/build_dataset_report.py` a partir de "
        "`data/processed/snowflake/manifest.json`."
    )
    lines.append("")
    lines.append("## Métricas de cabecera")
    lines.append("")
    lines.append(severity_block)
    lines.append("")
    lines.append("| Métrica | Valor |")
    lines.append("| --- | --- |")
    lines.append(f"| URLs descubiertas en sitemap (filtradas a secciones objetivo) | {manifest['total_discovered']} |")
    lines.append(f"| Documentos en el dataset (manifest) | {len(docs)} |")
    lines.append(f"| Documentos con archivo `.md` (success + skipped) | {total_docs_with_md} |")
    lines.append(f"| Descargados en este run | {manifest['total_downloaded']} |")
    lines.append(f"| Saltados (ya existían del piloto) | {manifest['total_skipped']} |")
    lines.append(f"| Fallidos | {manifest['total_failed']} |")
    lines.append(f"| Duración total | {manifest['duration_seconds']:.1f} s |")
    lines.append("")

    lines.append("## Distribución por sección")
    lines.append("")
    lines.append("| Sección | En manifest | Con `.md` generado |")
    lines.append("| --- | ---: | ---: |")
    for section in ("sql-reference", "migrations"):
        total = sum(1 for d in docs if d["section"] == section)
        ok = by_section_success.get(section, 0)
        lines.append(f"| `{section}` | {total} | {ok} |")
    lines.append("")

    lines.append("## Estadísticas de word_count (sobre documentos con `.md`)")
    lines.append("")
    lines.append("| Estadístico | Valor |")
    lines.append("| --- | ---: |")
    lines.append(f"| min | {min(wcs)} |")
    lines.append(f"| max | {max(wcs)} |")
    lines.append(f"| media | {statistics.mean(wcs):.1f} |")
    lines.append(f"| mediana | {int(statistics.median(wcs))} |")
    lines.append(f"| n | {len(wcs)} |")
    lines.append("")

    lines.append("## Definición de la métrica «heading vacío»")
    lines.append("")
    lines.append(
        "Un heading se considera **vacío** cuando se cumplen las dos condiciones siguientes:"
    )
    lines.append("")
    lines.append(
        "1. No hay contenido textual entre ese heading y el siguiente heading del documento."
    )
    lines.append(
        "2. El siguiente heading es del **mismo nivel o superior** "
        "(`##` seguido de `##`, o `###` seguido de `##`)."
    )
    lines.append("")
    lines.append(
        "La métrica es un proxy del contenido que el extractor no capturó "
        "(típicamente bloques de código)."
    )
    lines.append("")
    lines.append("### Por qué la condición (2)")
    lines.append("")
    lines.append(
        "Una primera versión **naive** de la métrica sólo aplicaba la condición (1): "
        "marcaba como vacío cualquier heading seguido de otro heading sin texto en medio, "
        "sin importar el nivel. Esa definición generaba **falsos positivos** con "
        "estructura jerárquica: un `## Padre` que arrancaba directamente con un "
        "`### Hijo` sin párrafo de introducción se contaba como vacío, aunque el "
        "contenido sí estaba presente dentro de las sub-secciones."
    )
    lines.append("")
    lines.append(
        f"Con la definición refinada actual, el dataset queda en **{empty_pct:.1f}%** "
        f"de documentos con al menos un heading vacío real "
        f"(umbral acordado ≤ {EMPTY_HEADING_THRESHOLD:.0f}%)."
    )
    lines.append("")
    lines.append("## Headings vacíos en el dataset")
    lines.append("")
    lines.append(severity_block)
    lines.append("")
    lines.append("| Métrica | Valor |")
    lines.append("| --- | ---: |")
    lines.append(f"| Documentos con ≥1 heading vacío | {len(files_with_empty)} / {total_docs_with_md} ({empty_pct:.1f}%) |")
    lines.append(f"| Total de headings vacíos (suma global) | {sum(len(t) for _, t in files_with_empty)} |")
    lines.append("")
    if top_titles:
        lines.append("**Top 10 títulos de heading vacío más frecuentes:**")
        lines.append("")
        lines.append("| Frecuencia | Título del heading |")
        lines.append("| ---: | --- |")
        for title, count in top_titles:
            lines.append(f"| {count} | `{title}` |")
        lines.append("")

    lines.append("## URLs descargadas")
    lines.append("")
    lines.append("| # | Sección | Words | Título | URL |")
    lines.append("| ---: | --- | ---: | --- | --- |")
    for i, (url, wc, section, title) in enumerate(sorted(rows, key=lambda x: (x[2], x[0])), 1):
        safe_title = title.replace("|", "\\|")
        lines.append(f"| {i} | `{section}` | {wc} | {safe_title or '—'} | <{url}> |")
    lines.append("")

    if failed:
        lines.append("## URLs fallidas")
        lines.append("")
        lines.append("| URL | Error |")
        lines.append("| --- | --- |")
        for d in failed:
            lines.append(f"| <{d['url']}> | {d.get('error_message', '—')} |")
        lines.append("")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"reporte escrito en {REPORT}")
    if breach:
        print(
            f"⚠️  empty_heading_pct = {empty_pct:.1f}% (> {EMPTY_HEADING_THRESHOLD:.0f}%): "
            "NO commitear hasta tomar decisión."
        )


if __name__ == "__main__":
    main()
