# Dataset report — scrape de docs.snowflake.com

Resumen del primer dataset piloto descargado en local desde `docs.snowflake.com`. Generado automáticamente por `scripts/build_dataset_report.py` a partir de `data/processed/snowflake/manifest.json`.

## Métricas de cabecera

> [!NOTE]
> **4.2%** de los documentos contienen al menos un heading vacío (umbral ≤ 10%).

| Métrica | Valor |
| --- | --- |
| URLs descubiertas en sitemap (filtradas a secciones objetivo) | 3067 |
| Documentos en el dataset (manifest) | 50 |
| Documentos con archivo `.md` (success + skipped) | 48 |
| Descargados en este run | 48 |
| Saltados (ya existían del piloto) | 0 |
| Fallidos | 2 |
| Duración total | 16.2 s |

## Distribución por sección

| Sección | En manifest | Con `.md` generado |
| --- | ---: | ---: |
| `sql-reference` | 30 | 30 |
| `migrations` | 20 | 18 |

## Estadísticas de word_count (sobre documentos con `.md`)

| Estadístico | Valor |
| --- | ---: |
| min | 116 |
| max | 21347 |
| media | 1157.8 |
| mediana | 384 |
| n | 48 |

## Definición de la métrica «heading vacío»

Un heading se considera **vacío** cuando se cumplen las dos condiciones siguientes:

1. No hay contenido textual entre ese heading y el siguiente heading del documento.
2. El siguiente heading es del **mismo nivel o superior** (`##` seguido de `##`, o `###` seguido de `##`).

La métrica es un proxy del contenido que el extractor no capturó (típicamente bloques de código).

### Por qué la condición (2)

Una primera versión **naive** de la métrica sólo aplicaba la condición (1): marcaba como vacío cualquier heading seguido de otro heading sin texto en medio, sin importar el nivel. Esa definición generaba **falsos positivos** con estructura jerárquica: un `## Padre` que arrancaba directamente con un `### Hijo` sin párrafo de introducción se contaba como vacío, aunque el contenido sí estaba presente dentro de las sub-secciones.

Con la definición refinada actual, el dataset queda en **4.2%** de documentos con al menos un heading vacío real (umbral acordado ≤ 10%).

## Headings vacíos en el dataset

> [!NOTE]
> **4.2%** de los documentos contienen al menos un heading vacío (umbral ≤ 10%).

| Métrica | Valor |
| --- | ---: |
| Documentos con ≥1 heading vacío | 2 / 48 (4.2%) |
| Total de headings vacíos (suma global) | 19 |

**Top 10 títulos de heading vacío más frecuentes:**

| Frecuencia | Título del heading |
| ---: | --- |
| 7 | `Example Code` |
| 3 | `Input Code:` |
| 3 | `Generated Code:` |
| 2 | `Oracle:` |
| 1 | `Code Example` |
| 1 | `SQL Server:` |
| 1 | `SQLServer:` |
| 1 | `Previous step` |

## URLs descargadas

| # | Sección | Words | Título | URL |
| ---: | --- | ---: | --- | --- |
| 1 | `migrations` | 171 | Snowflake Migration Tools | <https://docs.snowflake.com/en/migrations/README> |
| 2 | `migrations` | 334 | PNDSPY1011 | <https://docs.snowflake.com/en/migrations/sma-docs/issue-analysis/issue-codes-by-source/pandas/PNDSPY1011> |
| 3 | `migrations` | 302 | PNDSPY1026 | <https://docs.snowflake.com/en/migrations/sma-docs/issue-analysis/issue-codes-by-source/pandas/PNDSPY1026> |
| 4 | `migrations` | 295 | PNDSPY1104 | <https://docs.snowflake.com/en/migrations/sma-docs/issue-analysis/issue-codes-by-source/pandas/PNDSPY1104> |
| 5 | `migrations` | 271 | PNDSPY1144 | <https://docs.snowflake.com/en/migrations/sma-docs/issue-analysis/issue-codes-by-source/pandas/PNDSPY1144> |
| 6 | `migrations` | 271 | PNDSPY1148 | <https://docs.snowflake.com/en/migrations/sma-docs/issue-analysis/issue-codes-by-source/pandas/PNDSPY1148> |
| 7 | `migrations` | 282 | PNDSPY1149 | <https://docs.snowflake.com/en/migrations/sma-docs/issue-analysis/issue-codes-by-source/pandas/PNDSPY1149> |
| 8 | `migrations` | 323 | PNDSPY1201 | <https://docs.snowflake.com/en/migrations/sma-docs/issue-analysis/issue-codes-by-source/pandas/PNDSPY1201> |
| 9 | `migrations` | 265 | PNDSPY1216 | <https://docs.snowflake.com/en/migrations/sma-docs/issue-analysis/issue-codes-by-source/pandas/PNDSPY1216> |
| 10 | `migrations` | 643 | Snowpark Migration Accelerator: SMA Execution Guide | <https://docs.snowflake.com/en/migrations/sma-docs/use-cases/sma-checkpoints-walkthrough/sma-execution-guide/README> |
| 11 | `migrations` | 117 | Snowpark Migration Accelerator: Feature Settings | <https://docs.snowflake.com/en/migrations/sma-docs/use-cases/sma-checkpoints-walkthrough/sma-execution-guide/feature-settings/README> |
| 12 | `migrations` | 2007 | Snowpark Migration Accelerator: Readiness Scores | <https://docs.snowflake.com/en/migrations/sma-docs/user-guide/scos-conversion/readiness-scores> |
| 13 | `migrations` | 21347 | SnowConvert AI - General Issues | <https://docs.snowflake.com/en/migrations/snowconvert-docs/general/technical-documentation/issues-and-troubleshooting/conversion-issues/generalEWI> |
| 14 | `migrations` | 1200 | SnowConvert AI - Renaming feature | <https://docs.snowflake.com/en/migrations/snowconvert-docs/general/user-guide/snowconvert/command-line-interface/renaming-feature> |
| 15 | `migrations` | 1205 | SnowConvert AI - Hive - Built-in functions | <https://docs.snowflake.com/en/migrations/snowconvert-docs/translation-references/hive/built-in-functions> |
| 16 | `migrations` | 1081 | SnowConvert AI - Redshift - CONTINUE HANDLER | <https://docs.snowflake.com/en/migrations/snowconvert-docs/translation-references/redshift/redshift-continue-handler> |
| 17 | `migrations` | 116 | SnowConvert AI - Sybase IQ - CREATE TYPE | <https://docs.snowflake.com/en/migrations/snowconvert-docs/translation-references/sybase/sybase-create-type> |
| 18 | `migrations` | 550 | SnowConvert AI - Vertica - Predicates | <https://docs.snowflake.com/en/migrations/snowconvert-docs/translation-references/vertica/vertica-predicates> |
| 19 | `sql-reference` | 4408 | ACCESS_HISTORY view | <https://docs.snowflake.com/en/sql-reference/account-usage/access_history> |
| 20 | `sql-reference` | 311 | AGGREGATION_POLICIES view | <https://docs.snowflake.com/en/sql-reference/account-usage/aggregation_policies> |
| 21 | `sql-reference` | 539 | CREDENTIALS view | <https://docs.snowflake.com/en/sql-reference/account-usage/credentials> |
| 22 | `sql-reference` | 336 | NOTEBOOKS_CONTAINER_RUNTIME_HISTORY view | <https://docs.snowflake.com/en/sql-reference/account-usage/notebooks_container_runtime_history> |
| 23 | `sql-reference` | 515 | SEMANTIC_FACTS view | <https://docs.snowflake.com/en/sql-reference/account-usage/semantic_facts> |
| 24 | `sql-reference` | 344 | ANOMALY_INSIGHTS!GET_TOP_QUERIES_FROM_WAREHOUSE | <https://docs.snowflake.com/en/sql-reference/classes/anomaly-insights/methods/get_top_queries_from_warehouse> |
| 25 | `sql-reference` | 266 | <classification_profile_name>!SET_CLASSIFY_VIEWS | <https://docs.snowflake.com/en/sql-reference/classes/classification_profile/methods/set_classify_views> |
| 26 | `sql-reference` | 2363 | User-defined types | <https://docs.snowflake.com/en/sql-reference/data-types-user-defined> |
| 27 | `sql-reference` | 506 | Step 4: Link the API integration for Azure to the proxy service in the Portal | <https://docs.snowflake.com/en/sql-reference/external-functions-creating-azure-common-api-integration-proxy-link> |
| 28 | `sql-reference` | 708 | DYNAMIC_TABLE_GRAPH_HISTORY | <https://docs.snowflake.com/en/sql-reference/functions/dynamic_table_graph_history> |
| 29 | `sql-reference` | 296 | H3_LATLNG_TO_CELL_STRING | <https://docs.snowflake.com/en/sql-reference/functions/h3_latlng_to_cell_string> |
| 30 | `sql-reference` | 1182 | [ NOT ] IN | <https://docs.snowflake.com/en/sql-reference/functions/in> |
| 31 | `sql-reference` | 589 | INSERT | <https://docs.snowflake.com/en/sql-reference/functions/insert> |
| 32 | `sql-reference` | 747 | ONLINE_FEATURE_TABLE_REFRESH_HISTORY | <https://docs.snowflake.com/en/sql-reference/functions/online-feature-table-refresh-history> |
| 33 | `sql-reference` | 223 | RANDSTR | <https://docs.snowflake.com/en/sql-reference/functions/randstr> |
| 34 | `sql-reference` | 670 | SEARCH_OPTIMIZATION_HISTORY | <https://docs.snowflake.com/en/sql-reference/functions/search_optimization_history> |
| 35 | `sql-reference` | 292 | ST_DIFFERENCE | <https://docs.snowflake.com/en/sql-reference/functions/st_difference> |
| 36 | `sql-reference` | 186 | SYSTEM$CANCEL_ALL_QUERIES | <https://docs.snowflake.com/en/sql-reference/functions/system_cancel_all_queries> |
| 37 | `sql-reference` | 141 | SYSTEM$OPT_IN_INTERNAL_STAGE_NETWORK_LOGS | <https://docs.snowflake.com/en/sql-reference/functions/system_opt_in_internal_stage_network_logs> |
| 38 | `sql-reference` | 182 | SYSTEM$START_OAUTH_FLOW | <https://docs.snowflake.com/en/sql-reference/functions/system_start_oauth_flow> |
| 39 | `sql-reference` | 224 | Object identifiers | <https://docs.snowflake.com/en/sql-reference/identifiers> |
| 40 | `sql-reference` | 952 | ALTER APPLICATION PACKAGE | <https://docs.snowflake.com/en/sql-reference/sql/alter-application-package> |
| 41 | `sql-reference` | 1305 | ALTER SESSION POLICY | <https://docs.snowflake.com/en/sql-reference/sql/alter-session-policy> |
| 42 | `sql-reference` | 3801 | CREATE HYBRID TABLE | <https://docs.snowflake.com/en/sql-reference/sql/create-hybrid-table> |
| 43 | `sql-reference` | 1261 | CREATE SECRET | <https://docs.snowflake.com/en/sql-reference/sql/create-secret> |
| 44 | `sql-reference` | 425 | SHOW EXTERNAL FUNCTIONS | <https://docs.snowflake.com/en/sql-reference/sql/show-external-functions> |
| 45 | `sql-reference` | 272 | SHOW MAINTENANCE POLICIES | <https://docs.snowflake.com/en/sql-reference/sql/show-maintenance-policies> |
| 46 | `sql-reference` | 845 | SHOW RUN … IN EXPERIMENT | <https://docs.snowflake.com/en/sql-reference/sql/show-run-in-experiment> |
| 47 | `sql-reference` | 131 | UNDROP EXTERNAL VOLUME | <https://docs.snowflake.com/en/sql-reference/sql/undrop-external-volume> |
| 48 | `sql-reference` | 776 | SYSTEM$SEND_SNOWFLAKE_NOTIFICATION | <https://docs.snowflake.com/en/sql-reference/stored-procedures/system_send_snowflake_notification> |

## URLs fallidas

| URL | Error |
| --- | --- |
| <https://docs.snowflake.com/en/migrations/snowconvert-docs/general/getting-started/code-extraction/README> | ExtractionError: contenido demasiado corto (33 palabras < 100) |
| <https://docs.snowflake.com/en/migrations/snowconvert-docs/general/getting-started/running-snowconvert/review-results/README> | ExtractionError: contenido demasiado corto (56 palabras < 100) |
