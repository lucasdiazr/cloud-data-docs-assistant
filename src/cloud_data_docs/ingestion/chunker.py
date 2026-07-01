"""Chunking structure-aware de los documentos Markdown scrapeados.

Estrategia (decidida en el plan del Prompt 3):

1. Partir por estructura con `MarkdownHeaderTextSplitter` (#, ##, ###). Cada
   sección hereda su `heading_path` (p.ej. "Description > Syntax").
2. Si una sección supera `target_tokens`, sub-partirla con
   `RecursiveCharacterTextSplitter` usando separadores semánticos y midiendo
   longitud en TOKENS (tiktoken cl100k_base, el tokenizer de
   text-embedding-3-small), no en caracteres.
3. Mergear hacia el chunk anterior cualquier fragmento < `min_chunk_tokens`
   (los chunks diminutos son ruido en retrieval).

Mental model: "los headings deciden DÓNDE cortar; el límite de tokens decide
CUÁNTAS veces cortar dentro de una sección demasiado larga".
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import tiktoken
import yaml
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from pydantic import BaseModel, ConfigDict

# Tokenizer de text-embedding-3-small. cl100k_base se carga una sola vez por
# proceso (lazy) y se reutiliza.
_ENCODING_NAME = "cl100k_base"
_encoder: tiktoken.Encoding | None = None

# Cabeceras que abren chunk y su clave en la metadata del splitter.
_HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]
_HEADER_KEYS = ("h1", "h2", "h3")

# Separadores para el sub-split recursivo: de más a menos semántico.
_RECURSIVE_SEPARATORS = ["\n\n", "\n", ". ", " "]


def _get_encoder() -> tiktoken.Encoding:
    """Devuelve el encoder cl100k_base (cacheado a nivel de módulo)."""
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding(_ENCODING_NAME)
    return _encoder


def count_tokens(text: str) -> int:
    """Cuenta tokens de `text` con cl100k_base.

    Es la unidad canónica de longitud en todo el pipeline: chunking,
    estimación de coste y validación de rangos usan esta misma función.
    """
    return len(_get_encoder().encode(text))


class FrontMatter(BaseModel):
    """Metadatos YAML del frontmatter de un `.md` scrapeado."""

    model_config = ConfigDict(extra="ignore")

    url: str
    title: str
    section: str
    scraped_at: datetime
    word_count: int


class Chunk(BaseModel):
    """Fragmento listo para embeber e indexar."""

    model_config = ConfigDict(extra="forbid")

    content: str
    heading_path: str | None
    chunk_index: int
    token_count: int


def load_markdown_doc(path: Path) -> tuple[FrontMatter, str]:
    """Carga un `.md`, separa frontmatter YAML y devuelve `(FrontMatter, body)`.

    Args:
        path: Ruta al archivo Markdown con frontmatter delimitado por `---`.

    Returns:
        Tupla `(frontmatter, body)` con el cuerpo Markdown ya sin frontmatter.

    Raises:
        ValueError: Si el archivo no tiene un bloque de frontmatter válido.
    """
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise ValueError(f"{path} no empieza con frontmatter ('---')")

    # Frontmatter delimitado por la primera y la segunda línea '---'.
    parts = raw.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{path} tiene un frontmatter mal formado")

    _, front_raw, body = parts
    data = yaml.safe_load(front_raw)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: el frontmatter no es un mapping YAML")

    frontmatter = FrontMatter.model_validate(data)
    return frontmatter, body.lstrip("\n")


def _heading_path_from_metadata(metadata: dict[str, str]) -> str | None:
    """Construye 'h1 > h2 > h3' a partir de la metadata del header splitter.

    Solo incluye los niveles realmente presentes, en orden. Devuelve `None`
    para contenido sin heading (p.ej. preámbulo antes del primer `#`).
    """
    parts = [value for k in _HEADER_KEYS if (value := metadata.get(k))]
    return " > ".join(parts) if parts else None


def _split_by_headers(body: str) -> list[tuple[str, str | None]]:
    """Parte el body por headings. Devuelve lista de `(content, heading_path)`.

    `strip_headers=False`: cada sección conserva su línea de heading al inicio,
    lo que da contexto al embedding y evita un chunk "huérfano" sin título.
    """
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=_HEADERS_TO_SPLIT_ON,
        strip_headers=False,
    )
    sections = splitter.split_text(body)
    return [
        (doc.page_content, _heading_path_from_metadata(doc.metadata))
        for doc in sections
    ]


def _subsplit_oversized(
    content: str,
    target_tokens: int,
    overlap_tokens: int,
) -> list[str]:
    """Sub-parte una sección que excede `target_tokens` midiendo en tokens.

    Si la sección ya cabe en el presupuesto, se devuelve intacta.
    """
    if count_tokens(content) <= target_tokens:
        return [content]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=target_tokens,
        chunk_overlap=overlap_tokens,
        separators=_RECURSIVE_SEPARATORS,
        length_function=count_tokens,
        keep_separator=True,
    )
    return splitter.split_text(content)


def _merge_small_chunks(
    raw: list[tuple[str, str | None]],
    min_chunk_tokens: int,
) -> list[tuple[str, str | None]]:
    """Mergea fragmentos < `min_chunk_tokens` con su vecino.

    Un fragmento pequeño se funde con el anterior (conserva el heading_path del
    anterior). Caso borde: si el PRIMER fragmento es pequeño, se funde hacia
    adelante con el siguiente para no dejar ruido al inicio del documento.
    """
    if not raw:
        return []

    merged: list[tuple[str, str | None]] = []
    for content, heading_path in raw:
        if merged and count_tokens(content) < min_chunk_tokens:
            prev_content, prev_path = merged[-1]
            merged[-1] = (f"{prev_content}\n\n{content}", prev_path)
        else:
            merged.append((content, heading_path))

    # Fragmento líder pequeño: merge hacia adelante.
    if len(merged) > 1 and count_tokens(merged[0][0]) < min_chunk_tokens:
        c0, _ = merged[0]
        c1, h1 = merged[1]
        merged[1] = (f"{c0}\n\n{c1}", h1)
        merged.pop(0)

    return merged


def chunk_document(
    body: str,
    frontmatter: FrontMatter,
    target_tokens: int = 900,
    overlap_tokens: int = 120,
    min_chunk_tokens: int = 50,
) -> list[Chunk]:
    """Convierte el body Markdown de un documento en una lista de `Chunk`.

    Args:
        body: Cuerpo Markdown sin frontmatter.
        frontmatter: Metadatos del documento (no se incrusta aquí; lo usa el
            indexer para asociar cada chunk a su doc).
        target_tokens: Tamaño objetivo por chunk (las secciones que lo superan
            se sub-parten).
        overlap_tokens: Solape entre sub-chunks contiguos.
        min_chunk_tokens: Umbral por debajo del cual un chunk se mergea.

    Returns:
        Lista de `Chunk` con `chunk_index` consecutivo dentro del documento.
    """
    # frontmatter se acepta para fijar la firma del pipeline; los metadatos de
    # documento se asocian aguas abajo en el indexer.
    _ = frontmatter

    sections = _split_by_headers(body)

    # Sub-partir cada sección demasiado larga, preservando su heading_path.
    raw: list[tuple[str, str | None]] = []
    for content, heading_path in sections:
        for piece in _subsplit_oversized(content, target_tokens, overlap_tokens):
            stripped = piece.strip()
            if stripped:
                raw.append((stripped, heading_path))

    merged = _merge_small_chunks(raw, min_chunk_tokens)

    return [
        Chunk(
            content=content,
            heading_path=heading_path,
            chunk_index=index,
            token_count=count_tokens(content),
        )
        for index, (content, heading_path) in enumerate(merged)
    ]


__all__ = [
    "Chunk",
    "FrontMatter",
    "chunk_document",
    "count_tokens",
    "load_markdown_doc",
]
