# Journal técnico — Cloud Data Docs Assistant

Diario técnico del proyecto. Cada entrada documenta una sesión de trabajo: qué se hizo, qué se decidió y por qué, qué se aprendió, qué quedó pendiente.

Este archivo es parte del portfolio del proyecto.

---

## 2026-05-12 — Sesión 1: arranque y scaffolding del proyecto

### Qué hicimos

- Creado el repo en `~/Documents/projects/cloud-data-docs-assistant` y publicado en GitHub: https://github.com/lucasdiazr/cloud-data-docs-assistant.
- Inicializado proyecto Python 3.12 con **uv** y src layout. Paquetes vacíos: `ingestion`, `retrieval`, `generation`, `evaluation`, `api`, `frontend`, `common`.
- Añadidas las dependencias del stack RAG: `langchain`, `langchain-postgres`, `langchain-openai`, `langchain-anthropic`, `llama-index`, `openai`, `anthropic`, `cohere`, `psycopg[binary]`, `pgvector`, `sqlalchemy`, `fastapi`, `uvicorn[standard]`, `streamlit`, `pydantic`, `pydantic-settings`, `loguru`, `httpx`, `beautifulsoup4`, `lxml`, `tqdm`, `tiktoken`. Dev: `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`, `ipykernel`, `jupyter`, `ragas`.
- Configuración base: `pyproject.toml`, `.gitignore`, `.env.example`, `ruff.toml`, `.pre-commit-config.yaml`, `Makefile`, `README.md`.
- `docker-compose.yml` con servicio `postgres` (imagen `pgvector/pgvector:pg16`), healthcheck y volumen persistente. Servicio `langfuse` dejado comentado para fase posterior.
- `init-db.sql` que crea las extensiones `vector` y `pg_trgm` al primer arranque.
- Carpetas `data/{raw,processed,golden}`, `notebooks/`, `tests/`, `scripts/`, `docs/`.
- Módulos `common/config.py` (Pydantic Settings con `lru_cache`) y `common/logging.py` (loguru).
- Smoke test `tests/test_smoke.py` validando que el paquete y subpaquetes se importan.
- Generado `.env` con credenciales reales (3 API keys y password de Postgres aleatorio de 32 chars). Confirmado que `.env` está cubierto por `.gitignore` (línea 8).
- `scripts/verify_setup.py`: conecta a Postgres con las credenciales del `.env` y reporta versiones de las extensiones.
- Archivos de optimización de Claude Code: `CLAUDE.md` (instrucciones permanentes), `.claudeignore`, `.claude/settings.json` (esqueleto mínimo).

### Decisiones técnicas

- **LangChain como framework principal**. Razón: mayor demanda en ofertas de empleo en España y Europa para roles de AI Engineer; ecosistema maduro de integraciones y mejor cobertura en producción que LlamaIndex hoy. Trade-off conocido: abstracciones más pesadas que la API directa de los SDKs, pero buena ROI en términos de portabilidad de prompts y retrievers.
- **LlamaIndex como auxiliar**. Razón: su sistema de chunkers y `NodeParser` es más rico que el de LangChain para documentos estructurados (HTML/Markdown con headings). Lo usaremos para experimentar con estrategias de chunking sin acoplar a LangChain.
- **pgvector sobre PostgreSQL 16** como base vectorial. Razón: cercano al mundo enterprise español (muchas empresas ya operan Postgres), evita lock-in con vendor cloud (Pinecone, Weaviate, etc.), permite búsqueda híbrida fácil con `pg_trgm`, y es trivial de levantar local en Docker. Trade-off: rendimiento por debajo de bases vectoriales dedicadas a escalas muy grandes; irrelevante para este MVP.
- **Stack multi-provider desde el inicio**: `gpt-4o-mini` para experimentación e iteración (≈10x más barato que Claude para iterar prompts), Claude Sonnet (última versión vía API) para demo final y casos donde la calidad de respuesta importe. Útil además para el aprendizaje: tocar dos familias de modelos da perspectiva.
- **Embeddings con `text-embedding-3-small` de OpenAI**. Razón: relación coste/calidad excelente (1.536 dimensiones, ≈$0.02 / 1M tokens), gestionable en pgvector sin tunear índices agresivamente.
- **Cohere para re-ranking en fase avanzada**. Razón: estándar de facto, mejora notable de precisión sobre el top-k de retrieval inicial sin coste alto. Se introduce más tarde para aislar el efecto en las métricas.
- **Snowflake Cortex Search en semana 4 como capa comparativa**. Razón: nos da un baseline gestionado contra el cual comparar nuestro pipeline custom. Posponer hasta semana 4 evita quemar el **free trial de 30 días** de Snowflake antes de tiempo.
- **Deploy final en Azure Container Apps**. Razón: encaja con el perfil de empresas españolas, deploy basado en contenedores sin gestionar Kubernetes, escala a cero (paga sólo por uso real durante demo).
- **uv** en lugar de pip/Poetry. Razón: arranque rápido, lockfile reproducible (`uv.lock`), gestiona la versión de Python automáticamente, ya estándar de facto en proyectos Python modernos.
- **Estructura src layout** (no flat). Razón: evita conflictos entre el código instalado y el de desarrollo, fuerza importar el paquete instalado en tests.
- **`.env.local` para Postgres en lugar de un puerto distinto**. Cuando colisionó el puerto 5432 con otro contenedor (`retail_oltp`, abandonado), optamos por borrar el contenedor huérfano en lugar de cambiar el puerto: mantiene 5432 como puerto canónico y evita arrastrar configuración no estándar en herramientas GUI (DBeaver/pgAdmin).

### Conceptos nuevos

- **RAG (Retrieval Augmented Generation)**. Patrón en el que, antes de pedir al LLM que responda, recuperamos fragmentos relevantes de una base de conocimiento y los inyectamos en el prompt como contexto. Resultado: respuestas ancladas en fuentes verificables, menos alucinaciones, y posibilidad de actualizar el conocimiento sin reentrenar el modelo. Mental model: "el LLM hace la redacción, la base vectorial pone los hechos".

- **Embedding vectorial**. Representación numérica densa (un vector de N dimensiones, típicamente 384–3.072) de un texto, generada por un modelo entrenado para que textos semánticamente similares queden cerca en el espacio vectorial. Mental model: "coordenadas semánticas; sumas y restas tienen significado aproximado".

- **Vector database**. Base de datos optimizada para almacenar vectores y responder a la pregunta "¿qué N vectores son los más cercanos a este otro?" en latencias bajas. Usa estructuras como HNSW o IVFFlat para evitar el coste de comparar contra todos los registros. Mental model: "índice de búsqueda por similitud, no por igualdad".

- **pgvector**. Extensión de PostgreSQL que añade un tipo `vector` y operadores de distancia (`<->` L2, `<#>` producto interno, `<=>` coseno). Permite usar Postgres como vector DB sin servidor adicional, y combinar búsqueda vectorial con SQL relacional normal en la misma query. Para este proyecto, además, deja convivir búsqueda semántica con `pg_trgm` (trigramas) para keyword matching.

- **Chunking strategies**. Cómo partir documentos largos en fragmentos antes de embeber. Las opciones razonables: tamaño fijo con solapamiento, partido por estructura (headings, párrafos), o "semantic chunking" (parte donde cambia el tema). Mental model: "demasiado pequeño y pierdes contexto, demasiado grande y diluyes el embedding". Lo veremos en detalle en la sesión de ingesta.

- **Re-ranking**. Segunda pasada sobre el top-k recuperado por el vector search, usando un modelo más caro y preciso (típicamente un cross-encoder o servicio como Cohere Rerank) que reordena por relevancia. Mental model: "primer filtro rápido y grosero con vector search; segundo filtro caro y fino con re-ranking sobre los top-50".

- **Ragas (evaluación de RAG)**. Framework que evalúa pipelines RAG sobre cuatro ejes principales: `faithfulness` (la respuesta no contradice el contexto), `answer_relevancy` (responde lo preguntado), `context_precision` (lo recuperado es relevante) y `context_recall` (se recuperó todo lo necesario). Usa LLMs como jueces para puntuar. Mental model: "tests unitarios para el RAG, donde los asserts los hace un LLM".

- **LangChain vs LlamaIndex**. Dos frameworks que en parte se solapan. **LangChain** es más amplio: orquestación, agentes, integraciones, memorias, retrievers, prompt templates. **LlamaIndex** está más enfocado en la fase de indexación: data connectors variados, chunkers ricos, abstracciones de "índice" sobre los datos. La práctica común es elegir uno como principal y tomar piezas sueltas del otro cuando convenga.

### Atascos y resoluciones

- **Puerto 5432 ocupado en el primer `docker compose up`**. Otro contenedor (`retail_oltp`, postgres:16-alpine) lo tenía bindeado. Lo identificamos con `docker ps --filter "publish=5432"`. Solución: borrar el contenedor abandonado (`docker stop && docker rm`).
- **Contenedor healthy pero sin mapeo de puerto al host tras el primer `up`**. La columna `PORTS` salía vacía aunque el contenedor estaba healthy. Causa probable: el primer intento (que falló por puerto ocupado) creó el contenedor en un estado inconsistente y el segundo `up` no lo recreó. Solución: `docker compose down && docker compose up -d` fuerza recreación limpia. Aprendizaje: cuando algo se ve raro tras un fallo a medias, mejor un `down` completo que confiar en que el siguiente `up` repare.

### Configuración de Claude Code

- **`CLAUDE.md`**: instrucciones permanentes que Claude Code lee al inicio de cada sesión. Contiene contexto del usuario, stack canónico, convenciones, gestión de costes, política de comunicación (proponer opciones con trade-offs, no decidir en silencio) y, sobre todo, la regla de mantener el `JOURNAL.md`. Equivalente a un README pero dirigido al agente.
- **`.claudeignore`**: lista de patrones que el agente debe ignorar cuando inspecciona el repo (`.venv`, cachés, `data/raw`, `data/processed`, `uv.lock`, `node_modules`, etc.). Evita perder tiempo y contexto leyendo archivos masivos o irrelevantes.
- **`.claude/settings.json`**: archivo de configuración del agente para este repo. Por ahora sólo lleva el `$schema` apuntando al JSON Schema oficial; iteraremos sobre él cuando aparezcan necesidades concretas (permisos, hooks, etc.) en lugar de inventar campos.

### Métricas

- Smoke tests: **2/2 pasando**.
- Lint (`ruff check .`): **All checks passed**.
- PostgreSQL: **healthy** en ≈2s tras `compose up`.
- Extensiones detectadas: `vector` v0.8.2, `pg_trgm` v1.6.
- Coste de APIs gastado en esta sesión: **$0** (todo scaffolding, ninguna llamada a LLM ni embeddings).

### Pendiente

- **Prompt 2**: scraping y preparación del dataset de documentación oficial de Snowflake (y, en una segunda iteración, de Microsoft Learn para SQL Server).
- Decisiones a tomar al inicio del Prompt 2: alcance del scrape (URLs raíz), respeto de `robots.txt`, formato intermedio (`data/raw/` en HTML crudo o ya en Markdown).
