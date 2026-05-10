"""Configuración centralizada de logging basada en loguru.

Llamar `configure_logging()` una vez al arrancar la aplicación (FastAPI,
Streamlit o scripts CLI). Usa el nivel definido en `LOG_LEVEL`.
"""

from __future__ import annotations

import sys

from loguru import logger

from cloud_data_docs.common.config import get_settings

_DEFAULT_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)


def configure_logging(level: str | None = None) -> None:
    """Configura loguru con un único sink hacia stderr.

    Args:
        level: Si se indica, sobrescribe el nivel definido en `LOG_LEVEL`.
    """
    settings = get_settings()
    effective_level = (level or settings.log_level).upper()

    logger.remove()
    logger.add(
        sys.stderr,
        level=effective_level,
        format=_DEFAULT_FORMAT,
        backtrace=False,
        diagnose=False,
        enqueue=False,
    )


__all__ = ["configure_logging", "logger"]
