"""Clase base abstracta para scrapers asíncronos con rate limiting y reintentos.

Patrón de uso:

    async with SnowflakeScraper(...) as scraper:
        urls = await scraper.discover_urls()
        html = await scraper.download(url)
"""

from __future__ import annotations

import abc
import asyncio
import time
import urllib.robotparser
from pathlib import Path
from types import TracebackType
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from cloud_data_docs.common.logging import logger


class RateLimiter:
    """Rate limiter cooperativo basado en intervalo mínimo entre llamadas.

    Garantiza un máximo de `rate_per_second` adquisiciones por segundo. Usa
    un único timestamp protegido por un lock, lo que serializa el momento de
    cada request (la ejecución HTTP en sí puede solaparse vía Semaphore).
    """

    def __init__(self, rate_per_second: float) -> None:
        """Inicializa el limitador con una tasa máxima en req/s."""
        if rate_per_second <= 0:
            raise ValueError("rate_per_second debe ser > 0")
        self._min_interval = 1.0 / rate_per_second
        self._lock = asyncio.Lock()
        self._last_call: float = 0.0

    async def acquire(self) -> None:
        """Bloquea hasta que sea seguro emitir la siguiente petición."""
        async with self._lock:
            now = time.monotonic()
            wait = self._last_call + self._min_interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()


class BaseScraper(abc.ABC):
    """Esqueleto de scraper async con robots.txt, rate limit y reintentos.

    Las subclases implementan `discover_urls()` y `extract()`. La descarga,
    el rate limiting, la persistencia y la verificación de `robots.txt`
    quedan resueltas aquí.
    """

    def __init__(
        self,
        *,
        base_url: str,
        user_agent: str,
        raw_dir: Path,
        processed_dir: Path,
        rate_per_second: float = 5.0,
        concurrency: int = 5,
        timeout_seconds: float = 30.0,
    ) -> None:
        """Configura el scraper. El cliente HTTP se abre en `__aenter__`."""
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.raw_dir = raw_dir
        self.processed_dir = processed_dir
        self._rate_limiter = RateLimiter(rate_per_second)
        self._semaphore = asyncio.Semaphore(concurrency)
        self._timeout = timeout_seconds
        self._client: httpx.AsyncClient | None = None
        self._robots: urllib.robotparser.RobotFileParser | None = None

    async def __aenter__(self) -> BaseScraper:
        """Crea el cliente HTTP y carga `robots.txt`."""
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            headers={"User-Agent": self.user_agent},
            follow_redirects=True,
        )
        await self._load_robots()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Cierra el cliente HTTP."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _load_robots(self) -> None:
        """Carga y parsea `robots.txt`. Si falla, asume permitido (con warning)."""
        url = f"{self.base_url}/robots.txt"
        assert self._client is not None
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            parser = urllib.robotparser.RobotFileParser()
            parser.parse(resp.text.splitlines())
            self._robots = parser
            logger.info(f"robots.txt cargado desde {url}")
        except httpx.HTTPError as exc:
            logger.warning(
                f"no se pudo cargar robots.txt ({exc}). Se asume acceso permitido."
            )
            self._robots = None

    def can_fetch(self, url: str) -> bool:
        """Indica si `url` puede scrapearse según `robots.txt` (cargado en aenter)."""
        if self._robots is None:
            return True
        return self._robots.can_fetch(self.user_agent, url)

    async def _fetch(self, url: str) -> str:
        """GET con rate limit, concurrencia limitada y reintento exponencial."""
        assert self._client is not None, "scraper sin abrir (usar async with)"
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=10),
                retry=retry_if_exception_type(
                    (httpx.HTTPError, httpx.HTTPStatusError)
                ),
                reraise=True,
            ):
                with attempt:
                    await self._rate_limiter.acquire()
                    async with self._semaphore:
                        resp = await self._client.get(url)
                        resp.raise_for_status()
                        return resp.text
        except RetryError as exc:  # pragma: no cover (cubierto por reraise)
            last = exc.last_attempt.exception()
            if last is not None:
                raise last from exc
            raise
        raise RuntimeError("unreachable")

    async def download(self, url: str) -> str:
        """Descarga el HTML de `url` (público, alias semántico de `_fetch`)."""
        return await self._fetch(url)

    def save_raw_html(self, slug: str, html: str) -> Path:
        """Persiste HTML crudo en `raw_dir/<slug>.html`."""
        path = self.raw_dir / f"{slug}.html"
        path.write_text(html, encoding="utf-8")
        return path

    def save_markdown(self, slug: str, content: str) -> Path:
        """Persiste markdown limpio (con frontmatter) en `processed_dir/<slug>.md`."""
        path = self.processed_dir / f"{slug}.md"
        path.write_text(content, encoding="utf-8")
        return path

    @abc.abstractmethod
    async def discover_urls(self) -> list[tuple[str, str]]:
        """Devuelve la lista completa de (url, section) candidatas a scrapear."""

    @abc.abstractmethod
    async def extract(self, html: str, url: str) -> dict[str, Any]:
        """Extrae contenido limpio del HTML.

        El dict resultante debe incluir al menos `title`, `markdown_body`
        y `word_count`.
        """
