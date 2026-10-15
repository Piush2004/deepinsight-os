# Phase 4 - External Data Intelligence Platform

## Connector Architecture
DeepInsight OS employs an interface-driven connector architecture. Every platform integration (GA4, GSC, LinkedIn, etc.) inherits from the abstract `BaseConnector` class (`api.core.connectors.base.py`). 
This guarantees all connectors expose identical methods: `authenticate()`, `refresh_token()`, `sync()`, `normalize()`, `validate()`, and `disconnect()`. This decoupling ensures the background workers and Intelligence Layer never need to know the specifics of vendor APIs.

## OAuth Implementation
The OAuth flow is handled via the `Integrations` API Router. When the frontend redirects a user back with an `auth_code`, it hits `/{provider}/connect`. The system creates or updates an `Integration` record (tenant-aware via `client_id`) and passes the `auth_code` to the specific connector implementation. The connector then exchanges the code for a short-lived access token and a long-lived refresh token, which are stored securely in the `ConnectorToken` table.

## Normalization
Raw API data is never exposed to agents or the Knowledge Base. 
When `connector.sync()` pulls data, it immediately passes it through `connector.normalize()`. 
This function transforms vendor-specific JSON into a generic `NormalizedMetric` schema (e.g., mapping GA4's `sourceMedium` and GSC's `query` to a generic `dimension_1`). This abstraction allows the Intelligence Engine to analyze "Traffic" or "Search Performance" agnostically without knowing if the data came from Google or Bing.

## Knowledge Ingestion
Once metrics are normalized and stored in Postgres, the background sync worker calls `_ingest_to_knowledge_layer()`. This packages the normalized metrics into structural `KnowledgeDocument` records with enriched metadata and pushes them into the existing Knowledge Base architecture (triggering embeddings/pgvector ingestion automatically). This means agents can retrieve external data trends using standard similarity searches.

## Intelligence Enrichment
Immediately after Knowledge Ingestion, the Celery task triggers `_trigger_intelligence_layer()`. 
This acts as a pipeline hook for the Insight Engine to run business rule evaluation on the fresh data (e.g., detecting if traffic dropped 14% below baseline). It generates Confidence Scores and Risk Alerts, saving them as insights that agents can later inject into Monthly Reports.

## Celery Workflow
All syncs are asynchronous. A POST to `/{integration_id}/sync` dispatches a Celery task (`sync_integration_data` in `tasks.py`) to the `default` queue. 
The task:
1. Marks `IntegrationSync` as running.
2. Initializes the correct connector via `factory.py`.
3. Runs `sync()` -> `normalize()` -> DB Insertion.
4. Triggers Knowledge & Intelligence layers.
5. Uses `@retry(tenacity)` and Celery's `max_retries` for resilient fault tolerance against vendor rate limits.
6. Updates `ConnectorLog` for observability.

## Dashboard Updates
The Executive Command Center (`page.tsx`) now features a dynamic **Data Freshness** block under the Risk Alerts column. It displays exactly when each connected platform was last synced and whether the Knowledge Base holds 100% normalized data, driving transparency and trust for the end-user (agency CEO). Furthermore, a dedicated `/settings/integrations` page provides intuitive controls to Connect, Sync, or Disconnect individual platforms.

## Remaining Technical Debt
1. The OAuth flow is currently mocked in `ga4.py` and `gsc.py`. Actual Google API client libraries (`google-auth`, `google-api-python-client`) need to be integrated for the final production rollout.
2. Token encryption for `ConnectorToken` needs to be implemented using the existing `encryption_service` to ensure access/refresh tokens are encrypted at rest.
3. Actual Insight Engine heuristic rules for GA4/GSC need to be coded inside `_trigger_intelligence_layer`.
