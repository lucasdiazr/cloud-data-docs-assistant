# cloud-data-docs-assistant

> Asistente RAG que responde preguntas técnicas sobre la migración de **SQL Server → Snowflake** consultando documentación oficial pública (Microsoft Learn, Snowflake Docs y guías de migración).

---

## ¿Qué problema resuelve?

Migrar workloads de SQL Server a Snowflake implica cruzar centenares de páginas de documentación oficial repartidas entre dos vendors, con diferencias sutiles en tipos de datos, sintaxis SQL, funciones de fecha, cargas masivas, seguridad y administración.

Este asistente proporciona:

- **Respuestas técnicas verificables** ancladas en la documentación oficial (con citas y enlaces).
- **Comparativas SQL Server ↔ Snowflake** sobre tipos, funciones y sentencias equivalentes.
- **Reducción de tiempo de investigación** para equipos de datos durante la migración.

No reemplaza a un arquitecto de datos: actúa como compañero de búsqueda que cita la fuente para que la decisión final sea humana.

---

## Stack técnico

| Capa | Tecnología |
| --- | --- |
| Lenguaje / runtime | Python 3.12 + [`uv`](https://docs.astral.sh/uv/) |
| Orquestación RAG | LangChain (principal) + LlamaIndex (auxiliar) |
| Base vectorial | PostgreSQL 16 + `pgvector` (Docker) |
| Embeddings | OpenAI |
| LLM (experimentación) | OpenAI |
| LLM (demo final) | Anthropic (Claude) |
| Re-ranking | Cohere Rerank |
| API | FastAPI + Uvicorn |
| Frontend | Streamlit |
| Observabilidad | Langfuse (self-hosted) |
| Evaluación | Ragas |
| Calidad | Ruff, Mypy, Pytest, Pre-commit |

---

## Estructura del proyecto

```
cloud-data-docs-assistant/
├── src/cloud_data_docs/
│   ├── ingestion/      # Scraping y carga de documentación oficial
│   ├── retrieval/      # Búsqueda vectorial + re-ranking
│   ├── generation/     # Prompting y generación de respuestas con LLM
│   ├── evaluation/     # Pipelines de evaluación con Ragas
│   ├── api/            # FastAPI (endpoint /ask, etc.)
│   ├── frontend/       # Streamlit (UI de consulta)
│   └── common/         # Configuración, logging y utilidades compartidas
├── data/
│   ├── raw/            # HTML/Markdown crudo descargado (no se versiona)
│   ├── processed/      # Chunks listos para embeddings (no se versiona)
│   └── golden/         # Dataset de evaluación (Q&A de referencia)
├── notebooks/          # Exploración y prototipos
├── scripts/            # Utilidades de línea de comandos
├── tests/              # Tests con pytest
├── docs/               # SPEC.md y documentación interna
├── docker-compose.yml  # PostgreSQL + pgvector (y Langfuse en una fase posterior)
├── init-db.sql         # Crea las extensiones vector y pg_trgm al iniciar
├── pyproject.toml      # Metadata y dependencias gestionadas por uv
├── ruff.toml           # Configuración del linter/formatter
└── Makefile            # Atajos: install, lint, test, docker-up, docker-down…
```

---

## Setup local

Requisitos previos:

- macOS / Linux
- [`uv`](https://docs.astral.sh/uv/) instalado
- Docker daemon en marcha (en macOS funciona con [OrbStack](https://orbstack.dev/) como reemplazo de Docker Desktop)
- Python 3.12 (lo gestiona `uv` automáticamente)

### 1) Clonar e instalar dependencias

```bash
git clone <url-del-repo> cloud-data-docs-assistant
cd cloud-data-docs-assistant
make install
```

### 2) Configurar variables de entorno

```bash
cp .env.example .env
# Edita .env y rellena ANTHROPIC_API_KEY, OPENAI_API_KEY, COHERE_API_KEY
```

### 3) Levantar PostgreSQL + pgvector

```bash
make docker-up
```

Esto inicia un contenedor `postgres` con las extensiones `vector` y `pg_trgm` ya creadas (ver `init-db.sql`). Puerto expuesto: `5432`.

### 4) Comprobar que todo funciona

```bash
make test
```

---

## Comandos útiles

| Comando | Descripción |
| --- | --- |
| `make install` | Instala dependencias y hooks de pre-commit |
| `make lint` | Ejecuta `ruff check` y `mypy` |
| `make format` | Formatea con `ruff format` y aplica autofixes |
| `make test` | Lanza la suite de tests con `pytest` |
| `make docker-up` | Levanta PostgreSQL + pgvector |
| `make docker-down` | Detiene los servicios Docker |
| `make clean` | Limpia cachés y artefactos de build |

---

## Estado del proyecto

Fase actual: **scaffolding inicial**. Las implementaciones de ingesta, retrieval y generación llegarán por fases — ver [docs/SPEC.md](docs/SPEC.md) para el plan semanal.

---

## Licencia

MIT.
