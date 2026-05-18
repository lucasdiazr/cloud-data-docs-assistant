"""Scraper concreto para docs.snowflake.com.

Descubre URLs vía `/sitemap.xml` (manejando sitemap-index si lo hubiera) y
filtra por las secciones objetivo: `/en/sql-reference/` y `/en/migrate/`.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, ClassVar

from cloud_data_docs.common.logging import logger
from cloud_data_docs.ingestion.extractors.trafilatura_extractor import (
    extract_clean_text,
)
from cloud_data_docs.ingestion.scrapers.base import BaseScraper

SITEMAP_URL = "https://docs.snowflake.com/sitemap.xml"
SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


class SnowflakeScraper(BaseScraper):
    """Scraper específico de docs.snowflake.com."""

    SECTION_PATHS: ClassVar[dict[str, str]] = {
        "/en/sql-reference/": "sql-reference",
        "/en/migrations/": "migrations",
    }

    def _classify(self, url: str) -> str | None:
        """Devuelve la sección si la URL cae en una de las rutas objetivo."""
        for path, section in self.SECTION_PATHS.items():
            if path in url:
                return section
        return None

    async def _parse_sitemap(self, xml_text: str) -> tuple[bool, list[str]]:
        """Parsea XML de sitemap y devuelve `(is_index, urls)`.

        - Si la raíz es `sitemapindex`, `urls` son los sub-sitemaps.
        - Si la raíz es `urlset`, `urls` son las URLs finales.
        """
        root = ET.fromstring(xml_text)
        if root.tag.endswith("sitemapindex"):
            locs = [
                loc.text.strip()
                for loc in root.findall(f"{SITEMAP_NS}sitemap/{SITEMAP_NS}loc")
                if loc.text
            ]
            return True, locs
        locs = [
            loc.text.strip()
            for loc in root.findall(f"{SITEMAP_NS}url/{SITEMAP_NS}loc")
            if loc.text
        ]
        return False, locs

    async def discover_urls(self) -> list[tuple[str, str]]:
        """Descubre URLs candidatas leyendo el sitemap raíz y, si toca, sub-sitemaps."""
        logger.info(f"descargando sitemap raíz: {SITEMAP_URL}")
        root_xml = await self._fetch(SITEMAP_URL)
        is_index, entries = await self._parse_sitemap(root_xml)

        candidate_urls: list[str] = []
        if is_index:
            logger.info(f"sitemap-index con {len(entries)} sub-sitemaps")
            for sub_url in entries:
                try:
                    sub_xml = await self._fetch(sub_url)
                    _, sub_urls = await self._parse_sitemap(sub_xml)
                    candidate_urls.extend(sub_urls)
                except Exception as exc:
                    logger.warning(f"sub-sitemap fallido {sub_url}: {exc}")
        else:
            candidate_urls = entries

        filtered: list[tuple[str, str]] = []
        for url in candidate_urls:
            section = self._classify(url)
            if section is not None:
                filtered.append((url, section))

        logger.info(
            f"URLs totales: {len(candidate_urls)} | filtradas a secciones objetivo: "
            f"{len(filtered)}"
        )
        return filtered

    async def extract(self, html: str, url: str) -> dict[str, Any]:
        """Delega la extracción a trafilatura."""
        return extract_clean_text(html, url)
