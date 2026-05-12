# CLAUDE.md — instrucciones permanentes para Claude Code

Este archivo te lo lees al inicio de cada sesión. Son las reglas del proyecto y de la forma de trabajar con Lucas. No las repitas en pantalla salvo que te pregunten — síguelas.

---

## Contexto del proyecto

Este es un proyecto de aprendizaje **project-based**. El usuario es **Lucas**, data engineer senior basado en Madrid, con 7+ años de experiencia en SQL, ETL, Snowflake, Power BI y migraciones legacy. Está migrando profesionalmente desde Data Engineering hacia AI Engineering.

Es **experimentado en data pero relativamente nuevo en el stack moderno de IA** (LangChain, vector DBs, agentes, RAG). Adapta tus explicaciones a ese nivel: nada de explicarle qué es SQL, mucho de explicarle por qué eliges una estrategia de chunking sobre otra. Trátalo como un par técnico que sabe ingeniería de datos.

---

## Stack canónico del proyecto

- **Python 3.12** y **uv** para gestión de paquetes — NUNCA pip ni poetry.
- **LangChain** como framework principal de orquestación RAG.
- **LlamaIndex** como auxiliar para experimentar (chunkers más ricos, data connectors específicos).
- **PostgreSQL 16 + pgvector** vía Docker, gestionado con **OrbStack** en macOS. Los comandos `docker` y `docker compose` son drop-in. No intentes abrir Docker Desktop ni verificar su estado.
- **OpenAI API**: embeddings con `text-embedding-3-small` + LLM `gpt-4o-mini` para experimentación.
- **Anthropic API**: Claude Sonnet (última versión disponible vía API) para demo final y casos donde se requiera mejor calidad.
- **Cohere**: re-ranking en fase avanzada.
- **FastAPI** para backend, **Streamlit** para frontend de demo.
- **Langfuse self-hosted** para observability (fase posterior).
- **Ragas** para evaluación.
- **Snowflake Cortex Search** en semana 4 como capa comparativa.
- Deploy final en **Azure Container Apps**.

---

## Convenciones

- **Código y nombres de variables/funciones en inglés**.
- **Comentarios, docstrings y comunicación con el usuario en español**.
- **Type hints estrictos siempre.**
- **Pydantic v2** para data models y settings.
- **Loguru** para logging.
- **Ruff** para format/lint.
- **Pytest** para tests.

---

## Estructura del proyecto (src layout)

- `src/cloud_data_docs/ingestion/`: scraping, parsing, chunking, embeddings.
- `src/cloud_data_docs/retrieval/`: vector search, re-ranking, query transformation.
- `src/cloud_data_docs/generation/`: prompts, LLM calls, structured outputs.
- `src/cloud_data_docs/evaluation/`: Ragas, golden datasets, métricas.
- `src/cloud_data_docs/api/`: FastAPI endpoints.
- `src/cloud_data_docs/frontend/`: Streamlit app.
- `src/cloud_data_docs/common/`: config, logging, utilidades compartidas.
- `prompts/`: archivos `.md` con prompts de la aplicación. **NUNCA hardcodear prompts en código Python**.

---

## Gestión de costes (importante)

Este proyecto usa **APIs de pago**. Antes de ejecutar cualquier script que haga llamadas masivas a LLM o embeddings (**más de 50 llamadas, o más de $0.50 estimados**):

1. Calcula coste estimado con números (tokens × precio del modelo).
2. Muéstralo al usuario.
3. **Pide confirmación explícita** antes de ejecutar.

---

## Gestión de secretos

- Todas las credenciales vía `pydantic-settings` desde `.env`.
- **Nunca hardcodear secretos.**
- **Nunca subir `.env` a git.**
- Verifica `.gitignore` antes de cualquier commit relacionado con configuración.

---

## Modelos LLM por defecto

| Caso de uso | Modelo |
| --- | --- |
| Experimentación e iteración rápida | `gpt-4o-mini` (OpenAI) |
| Demo final / mejor calidad | Claude Sonnet (última versión disponible vía API) |
| Embeddings | `text-embedding-3-small` (OpenAI) |
| Re-ranking | `rerank-english-v3.0` (Cohere) o equivalente |

---

## Comunicación con el usuario

Esto es **project-based learning**. Tu rol es **ejecutar bien Y explicar el porqué de las decisiones**, no decidir en silencio.

Ante decisiones técnicas importantes (elección de librería, arquitectura, estrategia de chunking, modelo, etc.):

1. **Propón 2-3 opciones con trade-offs claros**.
2. Da tu recomendación con razón.
3. **Pide al usuario que elija** antes de implementar.

---

## Gestión del contexto

- Si una tarea va a requerir leer muchos archivos, lee primero los más críticos.
- **No leas archivos en `data/raw/` o `data/processed/`** a menos que el usuario lo pida explícitamente — pueden ser miles de chunks.
- Respeta `.claudeignore`.

---

## Dependencias

- **SIEMPRE usa `uv`** (`uv add`, `uv add --dev`, `uv sync`).
- Antes de añadir cualquier dependencia nueva, **pregunta al usuario para confirmar**.

---

## Testing

- Cualquier módulo nuevo significativo debe llevar tests con **pytest**.
- Tests mínimos pero presentes desde el inicio. Mejor un smoke test pasando que ninguno.

---

## MANTENIMIENTO DEL JOURNAL (instrucción crítica)

El proyecto tiene un archivo **`docs/JOURNAL.md`** que es un diario técnico del proyecto. Debes mantenerlo tú automáticamente con estas reglas:

### Cuándo escribir

- Al terminar **cada sesión de trabajo significativa** (al final de una fase, al cerrar un grupo de tareas, al completar un "PR mental"), añade una entrada nueva al final del JOURNAL.
- Al inicio de cada sesión nueva, **lee el final del JOURNAL.md** para retomar contexto rápido.

### Formato de cada entrada

Encabezado de fecha: `## YYYY-MM-DD — Título de la sesión`.

Secciones:

- **Qué hicimos**: lista breve de cambios reales.
- **Decisiones técnicas**: qué decidimos y **POR QUÉ**. La justificación es lo importante.
- **Conceptos nuevos**: si aparece un concepto técnico nuevo (RAG, embedding, chunking, re-ranking, etc.), explícalo en 2-4 frases con un **mental model claro**, no copia-pega de Wikipedia. Cuando un concepto ya aparezca en el journal, **NO vuelvas a definirlo**: solo referencia con "ver entrada de YYYY-MM-DD".
- **Atascos y resoluciones**: si algo falló o costó resolver, documéntalo brevemente. Esto es oro para futuras referencias.
- **Métricas** (cuando aplique): si la sesión incluye evaluación o medición, registra los números.
- **Pendiente**: qué queda para la próxima sesión.

### Tono del journal

Claro, conciso, en español, dirigido al **Lucas-futuro que va a releerlo en 3 meses para preparar una entrevista**. Nada de relleno corporativo. Si una decisión fue mala y se cambió, dilo: *"decidimos X, falló porque Y, cambiamos a Z"*.

### Cuidado al escribir

El JOURNAL.md **es un activo del portfolio**. Cuando esté completo, será una de las cosas que se enseñen en entrevistas. Escríbelo con ese nivel de cuidado.
