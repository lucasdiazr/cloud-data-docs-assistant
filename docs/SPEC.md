# SPEC — cloud-data-docs-assistant

> Versión preliminar. Documento vivo: se actualiza al final de cada semana.

---

## 1. Problema

Las migraciones de **SQL Server → Snowflake** obligan a equipos de datos a navegar dos cuerpos extensos de documentación oficial (Microsoft Learn y Snowflake Docs) para resolver dudas concretas: equivalencias de tipos, sintaxis SQL divergente, funciones de fecha y string, cargas masivas (`BCP`/`BULK INSERT` ↔ `COPY INTO`/Snowpipe), gestión de seguridad, particionado y rendimiento.

El proceso real combina lectura dispersa, búsquedas en Google y consultas a foros (Stack Overflow, comunidades Snowflake), con respuestas a menudo desactualizadas o sin cita verificable.

**Hipótesis de valor**: un asistente RAG centrado en la documentación oficial pública de ambos vendors reduce el tiempo de investigación y mejora la confianza en las respuestas (cita la fuente, sin alucinar APIs inexistentes).

---

## 2. Usuario objetivo

- **Ingenieros de datos / analytics engineers** que ejecutan o asisten una migración a Snowflake.
- **Arquitectos de datos** que diseñan la equivalencia de modelos entre on-prem (SQL Server) y cloud (Snowflake).
- **Consultores de migración** que necesitan respuestas rápidas con cita oficial para incluir en entregables.

Nivel asumido: SQL avanzado, familiaridad con conceptos de data warehousing.

---

## 3. No es objetivo

- No es un **traductor automático de DDL/DML** SQL Server → Snowflake (existen herramientas dedicadas como SnowConvert).
- No accede a **datos del cliente** ni se conecta a sus instancias reales.
- No reemplaza la **revisión humana** de un arquitecto: cita la fuente para que la decisión sea informada, no automática.
- No cubre **otras migraciones** (Oracle→Snowflake, Postgres→Snowflake, etc.) en esta versión.
- No es un **chatbot conversacional general**: el dominio está acotado a migración SQL Server ↔ Snowflake.

---

## 4. Arquitectura

### Flujo end-to-end

```
                ┌──────────────────────────┐
                │  Documentación oficial   │
                │  · Microsoft Learn       │
                │  · Snowflake Docs        │
                │  · Migration Guides      │
                └────────────┬─────────────┘
                             │ scraping (httpx + bs4/lxml)
                             ▼
                   ┌───────────────────┐
                   │   data/raw/       │  HTML/Markdown crudo
                   └─────────┬─────────┘
                             │ chunking (LangChain text splitters)
                             ▼
                   ┌───────────────────┐
                   │  data/processed/  │  chunks + metadata (vendor, url, sección)
                   └─────────┬─────────┘
                             │ embeddings (OpenAI)
                             ▼
              ┌────────────────────────────────┐
              │  PostgreSQL 16 + pgvector      │
              │  tabla: documents (vector)     │
              │  índice: HNSW / IVFFlat        │
              └────────────────┬───────────────┘
                               │
       Pregunta del usuario ───┤
                               ▼
                  ┌────────────────────────┐
                  │  Retrieval híbrido     │
                  │  · vector search       │
                  │  · BM25 / pg_trgm      │
                  └───────────┬────────────┘
                              ▼
                  ┌────────────────────────┐
                  │  Re-ranking (Cohere)   │
                  └───────────┬────────────┘
                              ▼
                  ┌────────────────────────┐
                  │  Generación (Claude)   │
                  │  prompt + contexto     │
                  └───────────┬────────────┘
                              ▼
                  ┌────────────────────────┐
                  │  Respuesta + citas     │
                  │  (FastAPI / Streamlit) │
                  └────────────────────────┘

           Trazas y métricas → Langfuse (self-hosted)
           Evaluación offline  → Ragas + dataset golden
```

### Componentes

| Módulo | Responsabilidad |
| --- | --- |
| `ingestion` | Descarga, parseo y chunking de la documentación oficial |
| `retrieval` | Búsqueda vectorial + híbrida + re-ranking |
| `generation` | Prompts, plantillas y llamadas al LLM |
| `evaluation` | Pipelines Ragas y curación del dataset golden |
| `api` | Endpoints FastAPI (`/ask`, `/health`, etc.) |
| `frontend` | UI Streamlit para demos y QA manual |
| `common` | Configuración tipada, logging, utilidades |

---

## 5. Métricas de éxito

**Calidad de respuesta** (medida con Ragas sobre dataset golden de ≥ 50 Q&A curadas a mano):

- `faithfulness` ≥ 0.85 — la respuesta no contradice los chunks recuperados.
- `answer_relevancy` ≥ 0.80 — la respuesta efectivamente responde la pregunta.
- `context_precision` ≥ 0.75 — los chunks recuperados son relevantes.
- `context_recall` ≥ 0.70 — se recuperan los chunks necesarios para responder.

**Citas**:

- ≥ 95% de las respuestas incluyen al menos una cita con URL oficial.
- 0 alucinaciones de URLs en sample manual de 30 respuestas.

**Operativas**:

- Latencia p95 end-to-end < 6 s (incluido re-ranking y LLM).
- Coste por consulta < 0,02 USD en demo final.

---

## 6. Stack

Ver `README.md` para la tabla completa. Decisiones clave:

- **uv** sobre pip/Poetry: arranque más rápido, lockfile reproducible, gestión de Python integrada.
- **LangChain + LlamaIndex**: LangChain como orquestador principal (más maduro en RAG en producción); LlamaIndex como auxiliar para data connectors específicos.
- **pgvector** sobre vector DB dedicada: Postgres ya cubre relacional + vectorial, simplifica operaciones para un MVP, permite búsqueda híbrida con `pg_trgm`.
- **Cohere Rerank**: estándar de facto para re-ranking ligero, mejora notablemente precisión sin coste alto.
- **OpenAI para experimentación, Anthropic para demo final**: comparar dos familias de modelos durante desarrollo y dejar Claude como front-facing por su calidad en respuestas técnicas largas con citas.
- **Langfuse self-hosted**: observabilidad sin compartir prompts con un servicio externo.

---

## 7. Plan semanal (4 semanas)

### Semana 1 — Fundamentos e ingesta

- Setup completo del proyecto (este scaffolding).
- Identificar fuentes de documentación oficial (URLs raíz por vendor).
- Implementar scraper en `ingestion/` con respeto de `robots.txt` y rate limiting.
- Persistir HTML/Markdown crudo en `data/raw/`.
- Primer pipeline de chunking sobre una sección piloto (ej. tipos de datos).

**Entregable**: script `python -m cloud_data_docs.ingestion.scrape` que produce ≥ 200 chunks listos en `data/processed/`.

### Semana 2 — Retrieval y vectorización

- Cargar chunks + embeddings (OpenAI `text-embedding-3-small`) a pgvector.
- Implementar búsqueda vectorial pura.
- Añadir búsqueda híbrida (vector + `pg_trgm` para keyword).
- Integrar Cohere Rerank.
- Construir dataset `data/golden/` inicial (≥ 30 Q&A).

**Entregable**: módulo `retrieval/` con función `search(query)` que devuelve top-k chunks con score y metadata.

### Semana 3 — Generación y API

- Diseñar prompts (system + few-shot) que fuercen citas.
- Integrar LLM (Anthropic) y formato de respuesta con citas.
- Exponer endpoint `POST /ask` en FastAPI.
- Construir UI Streamlit minimal (input + respuesta + chunks recuperados).
- Primer pase de evaluación Ragas sobre dataset golden.

**Entregable**: demo end-to-end funcionando localmente con `make docker-up` + FastAPI + Streamlit.

### Semana 4 — Evaluación, observabilidad, pulido

- Activar Langfuse (descomentar en `docker-compose.yml`) y trazar todo el pipeline.
- Cerrar dataset golden a ≥ 50 Q&A.
- Iterar sobre prompts y configuración de retrieval para alcanzar métricas objetivo.
- Documentar resultados en `docs/EVALUATION.md`.
- Grabar demo (Loom o similar) y publicar.

**Entregable**: repo con métricas Ragas reportadas, observabilidad en marcha y demo publicada.

---

## 8. Estimación de coste

**Desarrollo (4 semanas)** — costes de APIs, asumiendo uso moderado:

| Concepto | Estimación |
| --- | --- |
| OpenAI embeddings (`text-embedding-3-small`, ~5M tokens iniciales) | ~$0,10 |
| OpenAI generación durante experimentación (gpt-4o-mini, ~2M tokens) | ~$0,30 |
| Anthropic Claude (Sonnet, ~3M tokens entre desarrollo y demo) | ~$15-25 |
| Cohere Rerank (plan trial / pay-as-you-go, ~5k consultas) | ~$10 |
| Langfuse self-hosted | $0 (infraestructura local) |
| **Total estimado fase desarrollo** | **~$25-35 USD** |

**Operación post-demo** (si se usa puntualmente):

- Coste por consulta: embedding ~$0,00002 + retrieval (gratis local) + rerank ~$0,001 + Claude ~$0,01-0,02 → **~$0,01-0,02 por pregunta**.

Notas:

- Los precios de modelos cambian; revisar al cierre del proyecto.
- El coste se mantiene bajo porque la base vectorial corre en local; en producción habría que añadir hosting de Postgres y Langfuse.

---

## 9. Riesgos y mitigaciones

| Riesgo | Mitigación |
| --- | --- |
| Documentación oficial cambia frecuentemente | Reingestar periódicamente; almacenar `last_seen_at` por chunk |
| Rate limits del scraping | Respetar `robots.txt`, añadir backoff exponencial |
| Calidad pobre por chunking ingenuo | Probar varios tamaños y solapamientos; mantener metadata estructural (sección, headings) |
| Alucinaciones de URLs en respuestas | Validar post-generación que toda URL citada exista en los chunks recuperados |
| Coste descontrolado de embeddings | Cachear por hash de contenido; sólo re-embedeer chunks que cambiaron |
