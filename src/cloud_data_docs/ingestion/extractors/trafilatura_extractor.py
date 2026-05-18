"""Extractor de contenido limpio basado en trafilatura.

Convierte HTML de docs.snowflake.com a Markdown manteniendo enlaces y tablas,
y descartando boilerplate (menús, breadcrumbs, footers, banners de feedback).
"""

from __future__ import annotations

import re
from typing import Any

import trafilatura
from bs4 import BeautifulSoup

MIN_WORDS = 100
"""Mínimo de palabras para considerar la extracción válida."""

_ANCHOR_LINK_RE = re.compile(r"\[¶\]\([^)]*\)")
"""Anchor links de heading que añade Snowflake docs (`[¶](https://...#x)`)."""

_MULTI_BLANK_LINES_RE = re.compile(r"\n{3,}")
"""Tres o más saltos de línea consecutivos se colapsan a dos."""


def _clean_markdown(markdown: str) -> str:
    """Limpia el output de trafilatura de boilerplate específico de Snowflake docs.

    Elimina los anchor links `[¶](...)` y los caracteres pilcrow sueltos
    que Snowflake inserta junto a cada heading.
    """
    cleaned = _ANCHOR_LINK_RE.sub("", markdown)
    cleaned = cleaned.replace("¶", "")
    cleaned = _MULTI_BLANK_LINES_RE.sub("\n\n", cleaned)
    return cleaned.strip() + "\n"


def _clean_title(title: str) -> str:
    """Quita pilcrow y espacios sobrantes del título extraído."""
    return title.replace("¶", "").strip()


def _preprocess_snowflake_html(html: str) -> str:
    """Reemplaza los ``<div class="codeblock-wrapper">`` por ``<pre>`` limpios.

    Snowflake docs envuelve cada bloque de código en un wrapper con botones
    de UI ("Copy", "Expand"). Esa decoración hace que trafilatura clasifique
    el contenedor como boilerplate y descarte el ``<pre>`` interno. Aquí lo
    extraemos in-place: por cada wrapper, sustituimos todo el ``<div>`` por
    un ``<pre>`` que sólo contiene el texto del código.

    Args:
        html: HTML crudo de la página.

    Returns:
        HTML con los wrappers reemplazados por ``<pre>`` simples. Si el
        HTML no contiene wrappers, se devuelve sin modificar (early-return).
    """
    if not html or "codeblock-wrapper" not in html:
        return html
    soup = BeautifulSoup(html, "lxml")
    for wrapper in soup.select("div.codeblock-wrapper"):
        pre = wrapper.find("pre")
        if pre is None:
            continue
        text = pre.get_text("\n", strip=False)
        new_pre = soup.new_tag("pre")
        new_pre.string = text
        wrapper.replace_with(new_pre)
    return str(soup)


class ExtractionError(RuntimeError):
    """Se levanta cuando trafilatura no devuelve contenido útil."""


def extract_clean_text(html: str, url: str) -> dict[str, Any]:
    """Extrae título, body Markdown y conteo de palabras de un HTML.

    Args:
        html: HTML crudo de la página.
        url: URL de origen (mejora la metadata extraída).

    Returns:
        Diccionario con keys `title`, `markdown_body`, `word_count`.

    Raises:
        ExtractionError: si trafilatura no devuelve nada o el resultado
            tiene menos de `MIN_WORDS` palabras.
    """
    html = _preprocess_snowflake_html(html)
    markdown = trafilatura.extract(
        html,
        output_format="markdown",
        include_links=True,
        include_tables=True,
        url=url,
    )
    if not markdown:
        raise ExtractionError("trafilatura no devolvió contenido")

    markdown = _clean_markdown(markdown)
    word_count = len(markdown.split())
    if word_count < MIN_WORDS:
        raise ExtractionError(
            f"contenido demasiado corto ({word_count} palabras < {MIN_WORDS})"
        )

    metadata = trafilatura.extract_metadata(html)
    title: str | None = None
    if metadata is not None and getattr(metadata, "title", None):
        title = _clean_title(metadata.title)
    if not title:
        title = _title_from_url(url)

    return {
        "title": title,
        "markdown_body": markdown,
        "word_count": word_count,
    }


def _title_from_url(url: str) -> str:
    """Fallback simple: usa el último segmento de la URL como título."""
    last = url.rstrip("/").rsplit("/", 1)[-1]
    return last.replace("-", " ").replace("_", " ").strip().title() or "Untitled"
