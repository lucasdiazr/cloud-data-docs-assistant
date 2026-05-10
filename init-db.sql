-- Inicialización de extensiones de PostgreSQL para cloud-data-docs-assistant.
-- Este script lo ejecuta automáticamente la imagen oficial al primer arranque
-- (cuando el directorio de datos está vacío).

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
