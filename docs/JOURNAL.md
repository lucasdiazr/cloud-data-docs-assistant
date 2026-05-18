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

---

## 2026-05-18 — Sesión 2: pipeline de scraping Snowflake y dataset piloto de 50 docs

### Qué hicimos

- Construido el pipeline asíncrono de scraping en `src/cloud_data_docs/ingestion/`:
  - `models.py` — Pydantic v2: `ScrapedDocument`, `ScrapingResult`.
  - `scrapers/base.py` — `BaseScraper` async con `httpx.AsyncClient`, rate limiter (5 req/s), `Semaphore` de concurrencia y reintentos con `tenacity` (exponential backoff).
  - `scrapers/snowflake.py` — descubrimiento vía `sitemap.xml` con manejo de sitemap-index, clasificación por path.
  - `extractors/trafilatura_extractor.py` — extracción a Markdown con limpieza de pilcrow (`¶`) y anchor links rotos.
  - `pipeline.py` — orquestador, muestreo determinista 60/40 (`seed=42`), idempotencia por slug, fail-fast si >30% fallan, `manifest.json` al final.
  - `scripts/scrape_snowflake.py` — CLI con `typer` y resumen en `rich.Table`.
  - `scripts/reprocess_snowflake.py` — re-extrae los `.md` desde los HTML crudos sin tocar la red.
  - `scripts/build_dataset_report.py` — genera `docs/dataset-report.md` a partir del manifest.
- Tres deps nuevas: `trafilatura`, `tenacity`, `rich`.
- Dataset piloto cerrado: **48 `.md` finales** (de 50 URLs muestreadas; 2 son páginas reales con <100 palabras).
- `docs/dataset-report.md` generado con métricas, distribución, lista de URLs y definición explícita de la métrica de calidad.
- Tests del paquete `ingestion` en `tests/test_ingestion.py` (**11 tests**, todos en verde).

### Decisiones técnicas

- **Discovery vía `sitemap.xml`** en lugar de crawl recursivo. Razón: el sitemap es canónico, declara qué URLs deben ser indexables y evita falsos positivos (páginas duplicadas, traducciones a otros idiomas, snapshots históricos). Coste: una sola petición y parseo XML; sin riesgo de loops.
- **Rate limit a 5 req/s con `Semaphore(5) + RateLimiter` por intervalo mínimo**. Mantiene un perfil conservador (cumple con cualquier `Crawl-delay` razonable y respeta una infra que no es nuestra) sin necesidad de configurar nada por host.
- **`tenacity` para reintentos** (`stop_after_attempt(3)` + `wait_exponential`). Aísla la lógica de retry del flujo de extracción; las excepciones HTTP transitorias se reintentan, las de aplicación (`ExtractionError`) no.
- **Slug-as-filename derivado de la URL** (`en/sql-reference/sql/select` → `en__sql-reference__sql__select`). Reversible, único, idempotente. Esto da la idempotencia del pipeline: si existe `<slug>.md`, se marca `skipped`.
- **HTML crudo + Markdown limpio en dos carpetas distintas** (`data/raw/` vs `data/processed/`). Permite re-extraer sin re-pagar la red al cambiar el extractor (uso real: ver atascos).
- **Métrica de gate explícita en el reporte** (`empty_heading_pct ≤ 10%`) y fail-fast si el filtro `MIN_WORDS=100` deja más del 30% de URLs sin `.md`. Forzar el gate dentro del propio script de reporte evita commits que parecen verdes pero arrastran calidad sucia.

### Conceptos nuevos

- **Web scraping ético**. No es solo "respetar `robots.txt`": también identificarse con un User-Agent claro (`cloud-data-docs-assistant/0.1 (educational; github.com/lucasdiazr)`), no martillear (rate limiting), reintentar con backoff (no spam), almacenar el HTML crudo localmente para no re-descargar al iterar, y limitar el alcance a las secciones que de verdad necesitas. Mental model: "el dueño del servidor no debería notar tu paso por sus logs".

- **`robots.txt`**. Archivo en `https://<host>/robots.txt` que declara qué paths puede acceder un bot. La librería `urllib.robotparser` (stdlib) lo carga y permite preguntar `can_fetch(user_agent, url)`. Nuestro pipeline lo lee al entrar al `async with` del scraper y aborta si alguna URL objetivo está prohibida.

- **`sitemap.xml`**. Listado XML que el sitio publica declarando sus URLs canónicas. Puede ser un `urlset` (URLs finales) o un `sitemapindex` (índice de sub-sitemaps). En Snowflake es un urlset plano con ~7.600 entradas; filtramos las que están dentro de `/en/sql-reference/` y `/en/migrations/`.

- **`trafilatura`**. Extractor de "main content" especializado en páginas web. Recibe HTML, devuelve el texto principal sin menús, banners ni footers. Soporta salida en Markdown con enlaces y tablas. Su algoritmo es heurístico (scoring por densidad de texto, ratio link/texto, posición DOM), no perfecto: puede descartar bloques legítimos si están envueltos en decoración de UI (ver atascos).

- **Async + rate limiting con semáforos**. Combinación natural en Python para hacer scraping concurrente sin asfixiar al host: `asyncio.Semaphore(N)` limita cuántas peticiones están "in-flight" a la vez, un `RateLimiter` con `asyncio.Lock + timestamp` espacia los lanzamientos a una tasa máxima. Mental model: "Semaphore = N obreros; RateLimiter = obreros no cogen ticket más rápido que cada T segundos".

- **Idempotencia en pipelines de ingesta**. Propiedad de que ejecutar el mismo pipeline varias veces sobre los mismos inputs produce el mismo output, sin duplicar ni perder trabajo. La implementamos por "presence check" en el sistema de archivos: si existe el `.md` del slug, no se vuelve a descargar. Permite interrumpir y reanudar sin coste extra.

- **Refinamiento de métricas vs falsos positivos** (lección clave de esta sesión, ver atascos).

### Atascos y resoluciones

1. **Bug del path: `migrate` no existe, lo correcto es `migrations`.** En el primer piloto (5 docs) salieron los 5 de `sql-reference`. La causa: yo había filtrado por `/en/migrate/` pero el path real del sitemap es `/en/migrations/` (plural). Lo identifiqué inspeccionando los `<loc>` del sitemap directamente con `curl`. Corregido: `DocSection`, `SECTION_PATHS`, `_sample_balanced` y los tests. Resultado: 3.067 URLs filtradas en lugar de 2.320, ratio 60/40 sql-reference/migrations.

2. **`¶` y anchor links rotos en el output de trafilatura.** Snowflake añade un pilcrow `¶` a cada heading como anchor link visible. Trafilatura los preservaba en el Markdown final (`# Object identifiers[¶](https://docs.snowflake.com#object-identifiers)`). Solución: dos funciones `_clean_markdown` y `_clean_title` con regex que se aplican post-trafilatura. Cubierto con tests.

3. **Gate de calidad fallaba: 48.9% de docs con headings vacíos.** Tras descargar los 50 docs, mi métrica reportó que casi la mitad tenían al menos un heading sin contenido entre él y el siguiente. Patrón dominante: `## Syntax`, `## Generated Code:`, `## Example Code`. Diagnóstico (inspeccionando HTML crudo): los bloques de código de Snowflake están en `<div class="codeblock-wrapper">` con botones "Copy" y "Expand" alrededor del `<pre><code>`. Trafilatura los clasifica como boilerplate por la decoración UI y descarta el `<pre>` entero. **Solución**: pre-procesado del HTML con BeautifulSoup antes de pasarlo a trafilatura — por cada `codeblock-wrapper`, reemplazarlo por un `<pre>` simple con el texto del código. ~30 líneas de código nuevo en `_preprocess_snowflake_html`. Re-procesamos los 48 docs desde el HTML crudo (sin red, sin coste, 13.7 s).

4. **Tras el fix: 10.4%, sigue por encima del 10% — pero por la razón equivocada.** La métrica reportó 5 docs con headings vacíos restantes. Esperaba encontrar otro wrapper escondido (plan B documentado en §5 del plan original). Al inspeccionarlos descubrí que los 3 docs problemáticos de SnowConvert seguían estructura jerárquica: `## Sample Source Patterns` → `### CONTINUE HANDLER Conversion` (sin texto en medio, pero con contenido dentro de las sub-secciones). El `codeblock-wrapper` se estaba capturando correctamente (10/10 en `redshift-continue-handler`). Mi métrica naive contaba "vacío" cualquier `## X` seguido por otro `##+` sin texto, independientemente del nivel — y eso es un **falso positivo cuando el siguiente heading es un hijo**. Refiné la métrica: heading vacío sólo si el siguiente heading es del **mismo nivel o superior**. Con la métrica refinada: **4.2%** (2 docs / 48), gate cumplido con margen.

### Métricas

| Métrica | Antes del fix | Después del fix |
| --- | --- | --- |
| `empty_heading_pct` (naive) | 48.9% (22 / 45) | 10.4% (5 / 48) |
| `total_empty_headings` (naive) | 286 | 103 |
| `empty_heading_pct` (refined, oficial) | n/a | **4.2%** (2 / 48) |
| `total_empty_headings` (refined) | n/a | 19 |
| `word_count_mean` | 783.6 | 1.157.8 (+47.8 %) |
| `word_count_total` | 35.260 | 55.576 (+57.6 %) |
| Docs con `.md` final | 45 | 48 (+3 que antes no llegaban a 100 palabras) |
| Tests | 9 / 9 | **11 / 11** |
| Greps regresión (`¶`, `[¶](`) | n/a | **0 archivos** ✅ |
| Coste APIs | 0 USD | 0 USD |

### Lección clave

**Una métrica mal definida puede pasar o fallar un gate por razones equivocadas.** Cuando una métrica falla cerca del umbral (10.4% vs umbral 10%), el reflejo natural es "mejorar la solución para bajar 0.4 puntos". Pero antes hay que preguntarse: *¿la métrica está midiendo lo que quiero medir?* En este caso la respuesta era no: la métrica naive confundía estructura jerárquica con contenido faltante. Refinar la métrica reveló que el fix real (pre-procesado HTML) ya estaba completo, y que los 5 "vacíos" residuales eran ruido del sensor, no del extractor.

Regla operativa que me apunto: **antes de cambiar la solución cuando un gate falla por poco, validar la métrica con inspección manual de los casos límite**. Si la métrica está sesgada, refinarla y documentar el cambio (no esconderlo) es más barato y más correcto que sobre-ingenierizar la solución.

### Pendiente

- **Prompt 3**: chunking + embeddings + carga a `pgvector`. Decisiones a tomar al inicio: estrategia de chunking (tamaño/overlap, partido por estructura), modelo de embeddings (`text-embedding-3-small` por defecto), índice en pgvector (HNSW vs IVFFlat).
- Antes del Prompt 3, mirar si conviene normalizar espacios en el contenido extraído (Trafilatura introduce algunos espacios extra en código: `SYSTEM $ SEND_…` en lugar de `SYSTEM$SEND_…`).
