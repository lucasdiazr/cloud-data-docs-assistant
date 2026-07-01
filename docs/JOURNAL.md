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

---

## 2026-07-01 — Sesión 3: chunking, embeddings y carga a pgvector (Parte A)

Sesión larga y de cierre de fase. Objetivo: convertir los 48 `.md` en chunks vectorizados y cargarlos en pgvector, dejando el pipeline de ingesta listo para que el retrieval (Parte B) tenga de dónde tirar. A mitad apareció un bug de calidad de datos que obligó a un desvío de causa raíz; quedó documentado abajo porque es la parte más instructiva.

### Qué hicimos

- **Paquete `db/`** nuevo:
  - `connection.py` — `get_connection()` (psycopg síncrona) y `get_async_connection()`. Cero conexiones en import-time. Detalle no obvio: `Settings.postgres_dsn` está en formato SQLAlchemy (`postgresql+psycopg://`), que psycopg **crudo rechaza**; construimos el DSN nativo (`postgresql://`) desde los mismos campos.
  - `migrations.py` — `run_migrations(conn)` idempotente (todo `CREATE ... IF NOT EXISTS`): tabla `chunks`, índice HNSW `vector_cosine_ops`, índices btree en `section` y `doc_url`. No hace commit: lo decide el llamador.
- **`ingestion/chunker.py`** — chunking structure-aware (ver concepto abajo). `load_markdown_doc()` parsea frontmatter YAML + body; `chunk_document()` parte por headers, sub-parte por tokens y mergea los fragmentos diminutos. `count_tokens()` con tiktoken `cl100k_base` es la unidad canónica de longitud de todo el pipeline.
- **`ingestion/embedder.py`** — `embed_texts()` en batches de 100 con reintentos `tenacity`; `estimate_cost()` calcula tokens y coste **antes** de gastar (clave para la política de costes del proyecto).
- **`ingestion/indexer.py`** — orquesta carga→chunk→coste→embeddings→upsert. `dry_run` corta antes de OpenAI/DB. Idempotencia vía `ON CONFLICT (doc_url, chunk_index) DO UPDATE` + **limpieza de huérfanos** (ver decisiones).
- **`scripts/index_dataset.py`** — CLI typer: `--dry-run`, `--pilot` (5 docs, seed 42), o completo. Tabla `rich` de resumen.
- **Fix de calidad de datos** en `extractors/trafilatura_extractor.py` + reproceso de los 48 `.md` (el desvío de esta sesión).
- Tests nuevos: `test_chunker.py` (5), `test_embedder.py` (5), +2 en `test_ingestion.py`. Suite total: **22 verde**.

### Decisiones técnicas

- **Chunking structure-aware, no tamaño fijo.** Partimos primero por headings (`#`/`##`/`###`) con `MarkdownHeaderTextSplitter` y solo sub-partimos (con `RecursiveCharacterTextSplitter`) las secciones que superan el target. Razón: en documentación de referencia, la unidad semántica natural es la sección (una función, un parámetro, un ejemplo). Cortar por tamaño fijo mezclaría el final de una sección con el principio de otra y ensuciaría el embedding. **Consecuencia medida y aceptada**: la mayoría de chunks quedan por debajo del target de 900 (mediana ~233 tokens) porque las secciones de Snowflake son cortas. El "900" actúa como techo, no como objetivo. Damos por buena la coherencia semántica sobre la uniformidad de tamaño; si el retrieval sufre, lo reajustamos con datos de Ragas, no por intuición.
- **Medir longitud en tokens, no en caracteres.** `RecursiveCharacterTextSplitter` usa `length_function=count_tokens`, de modo que `chunk_size`/`overlap` se expresan en tokens con el **mismo tokenizer que el modelo de embeddings** (`cl100k_base`). Así el presupuesto de chunk se alinea con lo que de verdad consume el embedding.
- **Índice HNSW con `vector_cosine_ops`** (ver definición de vector DB / HNSW, entrada 2026-05-12). Elegimos coseno porque los embeddings de OpenAI vienen normalizados y es la métrica estándar para similitud semántica. HNSW sobre IVFFlat: mejor recall a coste de más memoria; irrelevante a esta escala (318 vectores).
- **Idempotencia por upsert + limpieza de huérfanos.** `ON CONFLICT DO UPDATE` evita duplicados al re-indexar. Pero descubrimos un caso que el upsert **no** cubre: si un doc pasa de 6 a 4 chunks (porque el texto cambió), las filas con `chunk_index` 4 y 5 del run anterior quedan **huérfanas** — el upsert solo toca 0..N-1. Solución integrada en el indexer: tras insertar, por cada doc `DELETE WHERE chunk_index >= nuevo_count`, todo en la **misma transacción**. Preventivo, no reactivo.
- **Estimación de coste antes de gastar.** El indexer calcula tokens×precio y (si supera umbral) pide confirmación. Coste real de indexar los 48: **$0.0019**. Trivial, pero el patrón es lo que importa de cara a corpus más grandes.
- **Fix de extracción sobre fix de reparación.** Ante el bug de espacios (abajo), la regla que seguimos: preferir que el espacio nunca se genere (arreglar la extracción) antes que quitarlo con regex después. Más robusto y sin riesgo de corromper prosa.

### Conceptos nuevos

- **Chunking structure-aware.** Estrategia de chunking (ver concepto general, entrada 2026-05-12) que usa la estructura del documento como guía de corte. Mental model: **"los headings deciden DÓNDE cortar; el límite de tokens decide CUÁNTAS veces cortar dentro de una sección demasiado larga"**. El overlap solo aplica al sub-partir secciones largas, no entre secciones distintas (ahí el límite ya es semántico).

- **`tiktoken` y por qué medir en tokens.** El tokenizer que usa el modelo. Un token ≈ 4 caracteres en inglés, pero varía mucho con código y símbolos. Medir chunks en tokens (y no en caracteres o palabras) alinea el tamaño del chunk con el límite real del modelo y con el coste (que se factura por token). `cl100k_base` es el de `text-embedding-3-small` y de la familia GPT-4.

- **Upsert (`ON CONFLICT DO UPDATE`) y chunks huérfanos.** Upsert = "inserta, y si ya existe (viola un UNIQUE), actualiza". Da idempotencia barata. El gotcha de los **huérfanos**: cuando la clave natural es compuesta y posicional (`doc_url` + `chunk_index`) y el número de posiciones puede **encoger** entre runs, las posiciones sobrantes del run viejo sobreviven al upsert. Mental model: "el upsert pisa lo que vuelves a escribir, pero no barre lo que ya no escribes". Hay que barrerlo aparte.

- **`<wbr>` (word break opportunity).** Tag HTML zero-width que marca dónde un navegador **puede** romper una palabra larga si no cabe. No añade texto visible. Relevante aquí porque distintos extractores lo tratan distinto: BeautifulSoup lo ignora en `get_text()`, pero trafilatura lo convierte en un espacio real (ver atasco).

### Atascos y resoluciones

**El bug de los espacios: investigación de causa raíz.** En la validación del piloto, los chunks mostraban dos tipos de ruido: identificadores partidos en headings (`SYSTEM$SEND_ SNOWFLAKE_ NOTIFICATION`) y código con espacios espurios (`ARRAY [ 1 , 2 , 3 ]`). En lugar de tapar con regex, fuimos a la causa raíz en el HTML crudo (con BeautifulSoup):

1. **Headings.** `h1.get_text()` daba el identificador **limpio** — el HTML no tenía los espacios. Los introducía **trafilatura** al convertir los `<wbr/>` (que Snowflake mete dentro de identificadores largos) en espacios. Fix: `decompose()` de los `<wbr>` en el pre-procesado HTML, antes de trafilatura.
2. **Código.** Los `<pre>` traían el código troceado en spans de syntax-highlighting (`<span class="hljs-keyword">ANY</span><span class="hljs-punctuation">(</span>...`). Nuestro `_preprocess_snowflake_html` los unía con `pre.get_text("\n", strip=False)` → un salto de línea entre **cada** token → trafilatura, que no los trata como bloque de código (los `.md` no usan fenced blocks), re-unía esas líneas con espacios. Fix: `pre.get_text("")` (sin separador) → los tokens se concatenan tal cual y solo sobreviven los saltos de línea reales del código.

Ambos fixes se validaron end-to-end sobre los 2 HTML reales antes de tocar el módulo. Después: reproceso de los 48 `.md` desde HTML crudo (sin red, $0, 14 s), verificación por greps (0 headings partidos, 0 regresión de pilcrow, `ARRAY[1, 2, 3]` correcto), y variación de `word_count` de **−8.83%** (esperado: menos espacios = menos "palabras", dentro del margen ±10%).

**Verificación de string literals.** Preocupación explícita: que la normalización no rompiera literales entre comillas. Confirmado en un chunk de `CREATE SECRET`: `OAUTH_SCOPES = ('useraccount') COMMENT = 'secret for the service now connector'` queda intacto. El fix de extracción no toca prosa ni strings porque opera solo dentro de `<pre>` y sobre `<wbr>`.

### Métricas

| Métrica | Valor |
| --- | --- |
| Docs indexados | 48 |
| Chunks totales en `chunks` | **318** (295 creados + 23 actualizados) |
| Distribución | migrations 166 / sql-reference 152 |
| Tokens (chunk): min / mediana / max | 50 / 233 / 964 |
| Tokens totales embebidos | 94.152 |
| Coste real acumulado (embeddings) | **$0.0019** |
| `word_count` corpus antes → después del reproceso | 55.576 → 50.669 (−8.83%) |
| Huérfanos / duplicados en DB | 0 / 0 |
| Tests | **22 / 22** verde |
| Ruido residual (heading_path / content) | 0 / 0 |

### Lección clave

**El fix del Prompt 2 introdujo este bug, y los gates de aquel momento no lo detectaron.** El pre-procesado de `codeblock-wrapper` (Sesión 2) fue lo que empezó a extraer el código de los `<pre>` — y con él, el `get_text("\n")` que fragmentaba los tokens. Aquel gate medía *headings vacíos* (¿capturamos el bloque de código?), y lo pasaba: el código **sí** se capturaba. Pero nadie medía la *integridad del espaciado* de ese código. **Un gate mide lo que mide; pasar un gate no es "está bien", es "está bien en la dimensión que ese gate observa".** Regla que me llevo, complementaria a la de la Sesión 2 (validar la métrica): **cuando un fix cambia una salida, añade un gate que observe la nueva dimensión que ese fix podría romper.** El fix de código necesitaba un gate de espaciado, no solo de "hay código".

Segundo apunte, de método: **ir a causa raíz en el HTML crudo antes de escribir un solo regex** ahorró un fix frágil. La diferencia entre BeautifulSoup (ignora `<wbr>`) y trafilatura (lo vuelve espacio) solo se ve mirando el dato, no razonando desde el markdown ya corrupto.

### Pendiente

- **Parte B del Prompt 3**: retrieval. Vector search sobre `chunks` (similitud coseno con el índice HNSW), query transformation, y montar el primer bucle RAG de punta a punta (retrieval → prompt → LLM). Decisiones a tomar al inicio: `top_k` de recuperación, si añadir búsqueda híbrida con `pg_trgm` desde ya o dejarlo para después, y qué modelo de generación usar para las primeras pruebas (`gpt-4o-mini` por defecto).
- Cuando entre re-ranking (Cohere), medir el delta de precisión con Ragas contra el baseline sin re-rank.
