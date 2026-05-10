"""Smoke test: verifica que el paquete principal se importa correctamente."""

from __future__ import annotations


def test_package_imports() -> None:
    """El paquete raíz se importa y expone su versión."""
    import cloud_data_docs

    assert hasattr(cloud_data_docs, "__version__")
    assert isinstance(cloud_data_docs.__version__, str)


def test_subpackages_import() -> None:
    """Todos los subpaquetes definidos se importan sin errores."""
    from cloud_data_docs import (
        api,
        common,
        evaluation,
        frontend,
        generation,
        ingestion,
        retrieval,
    )

    assert all(
        pkg is not None
        for pkg in (api, common, evaluation, frontend, generation, ingestion, retrieval)
    )
