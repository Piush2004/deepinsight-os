import datetime
import logging
import uuid
import uuid as uuid_module

from api.core.celery_app import celery_app
from api.core.connectors.factory import get_connector
from api.core.interfaces.llm_provider import LLMGenerationError, LLMUnavailableError
from api.database.session import SessionLocal
from api.models.integrations import ConnectorLog, Integration, IntegrationSync, NormalizedMetric

logger = logging.getLogger(__name__)


def _build_reporting_agent(client_id, task_id, db):
    """Constructs a ReportingAgent with real, non-mocked collaborators - the concrete
    OllamaProvider, real pgvector-backed retrieval, and the real Intelligence Layer.
    Centralized here so the Celery task and any synchronous caller build it identically.

    client_id is cast to a real uuid.UUID below (Celery tasks receive it as a plain
    str, per their own type hints, since Celery serializes args as JSON) - a real
    Postgres server accepts a plain string bound against a UUID column transparently,
    but SQLite's bind processor for the same postgresql.UUID column type does not
    (raises AttributeError: 'str' object has no attribute 'hex'), which is exactly why
    this was never caught before VECTOR_STORE_PROVIDER=memory dev/demo mode started
    actually exercising this path against SQLite."""
    from api.core.agent.reporting_agent import ReportingAgent
    from api.services.llm.ollama_provider import OllamaProvider
    from api.services.prompt_service import PromptService
    from api.services.intelligence.engine import IntelligenceLayer
    from api.services.knowledge.embeddings import get_embedding_provider
    from api.services.knowledge.vector_store import get_vector_store
    from api.services.knowledge.retrieval import PgVectorRetriever, RagKnowledgeQueryService

    retriever = PgVectorRetriever(get_embedding_provider(), get_vector_store(db), db)
    return ReportingAgent(
        client_id=uuid.UUID(str(client_id)),
        task_id=task_id,
        llm=OllamaProvider(),
        knowledge_query=RagKnowledgeQueryService(retriever),
        prompt_service=PromptService(base_dir="prompts"),
        intelligence=IntelligenceLayer(),
        db=db,
    )


def _build_content_agent(client_id, task_id, db):
    """Mirrors _build_reporting_agent for the Content Agent - same real collaborators."""
    from api.core.agent.content_agent import ContentAgent
    from api.services.llm.ollama_provider import OllamaProvider
    from api.services.prompt_service import PromptService
    from api.services.intelligence.engine import IntelligenceLayer
    from api.services.validation.content_quality import ContentQualityEngine
    from api.services.knowledge.embeddings import get_embedding_provider
    from api.services.knowledge.vector_store import get_vector_store
    from api.services.knowledge.retrieval import PgVectorRetriever, RagKnowledgeQueryService

    retriever = PgVectorRetriever(get_embedding_provider(), get_vector_store(db), db)
    return ContentAgent(
        client_id=uuid.UUID(str(client_id)),
        task_id=task_id,
        llm=OllamaProvider(),
        knowledge_query=RagKnowledgeQueryService(retriever),
        prompt_service=PromptService(base_dir="prompts"),
        intelligence=IntelligenceLayer(),
        quality_engine=ContentQualityEngine(),
        db=db,
    )


def _build_seo_agent(client_id, task_id, db):
    """Mirrors _build_reporting_agent/_build_content_agent for the SEO Agent - same
    real collaborators, plus the real (dev-fixture-backed, see
    api/services/seo/provider_factory.py) SEODataProvider."""
    from api.core.agent.seo_agent import SEOAgent
    from api.services.llm.ollama_provider import OllamaProvider
    from api.services.prompt_service import PromptService
    from api.services.intelligence.engine import IntelligenceLayer
    from api.services.knowledge.embeddings import get_embedding_provider
    from api.services.knowledge.vector_store import get_vector_store
    from api.services.knowledge.retrieval import PgVectorRetriever, RagKnowledgeQueryService
    from api.services.seo.provider_factory import get_seo_data_provider

    retriever = PgVectorRetriever(get_embedding_provider(), get_vector_store(db), db)
    return SEOAgent(
        client_id=uuid.UUID(str(client_id)),
        task_id=task_id,
        llm=OllamaProvider(),
        knowledge_query=RagKnowledgeQueryService(retriever),
        prompt_service=PromptService(base_dir="prompts"),
        intelligence=IntelligenceLayer(),
        seo_data_provider=get_seo_data_provider(),
        db=db,
    )


@celery_app.task(bind=True, max_retries=3)
def process_seo_analysis(self, client_id: str, period_start: str, period_end: str):
    """
    Background job that runs the real SEOAgent end to end (SEODataProvider ->
    deterministic rule engine -> opportunity scoring -> client knowledge context -> LLM
    strategic explanation -> Evaluation Engine -> persist SEOAnalysis/SEOOpportunity/
    SEOApprovalRequest rows). Same retry/no-retry split as report/content generation:
    a validation failure (e.g. the quality gate rejecting a fabricated number) will
    fail identically on retry, so it isn't retried.
    """
    logger.info(f"Starting SEO analysis for client {client_id}, period {period_start}..{period_end}")
    db = SessionLocal()
    try:
        agent = _build_seo_agent(client_id, uuid_module.uuid4(), db)
        agent.run(period_start=period_start, period_end=period_end)
        analysis_id = str(agent.analysis.id) if agent.analysis else None
        logger.info(f"Completed SEO analysis for client {client_id}, analysis {analysis_id}")
        return {"status": "success", "analysis_id": analysis_id}
    except (ValueError, LLMGenerationError) as exc:
        logger.error(f"SEO analysis validation failed for client {client_id}: {exc}")
        raise
    except LLMUnavailableError as exc:
        logger.error(f"LLM unavailable during SEO analysis for client {client_id}: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
    except Exception as exc:
        logger.error(f"Error running SEO analysis for client {client_id}: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def process_content_generation(self, client_id: str, content_type: str, target_audience: str,
                                goal: str, content_id: str = None, title: str = None):
    """
    Background job that runs the real ContentAgent end to end (retrieve knowledge ->
    Intelligence Layer -> LLM -> brand voice validation -> quality scoring -> persist ->
    approval queue). Same retry/no-retry split as process_report_generation.
    """
    logger.info(f"Starting content generation for client {client_id}, type {content_type}")
    db = SessionLocal()
    try:
        agent = _build_content_agent(client_id, uuid_module.uuid4(), db)
        agent.run(content_type=content_type, target_audience=target_audience, goal=goal,
                  content_id=content_id, title=title)
        logger.info(f"Completed content generation for client {client_id}, content {agent.content.id}")
        return {"status": "success", "content_id": str(agent.content.id)}
    except (ValueError, LLMGenerationError) as exc:
        logger.error(f"Content generation validation failed for client {client_id}: {exc}")
        raise
    except LLMUnavailableError as exc:
        logger.error(f"LLM unavailable during content generation for client {client_id}: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
    except Exception as exc:
        logger.error(f"Error generating content for client {client_id}: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def process_report_generation(self, client_id: str, reporting_period: str, metrics: dict,
                               historical_metrics: dict = None):
    """
    Background job that runs the real ReportingAgent end to end (gather context ->
    Intelligence Layer -> LLM -> validate -> persist Report/ReportVersion/ApprovalRequest).
    Retries on transient LLM/DB failures; does NOT retry on agent-side validation
    failures (bad input, failed quality gate) since retrying with the same input
    would just fail the same way.
    """
    logger.info(f"Starting report generation for client {client_id}, period {reporting_period}")
    db = SessionLocal()
    try:
        agent = _build_reporting_agent(client_id, uuid_module.uuid4(), db)
        agent.run(metrics=metrics, historical_metrics=historical_metrics, reporting_period=reporting_period)
        logger.info(f"Completed report generation for client {client_id}, report {agent.report.id}")
        return {"status": "success", "report_id": str(agent.report.id)}
    except (ValueError, LLMGenerationError) as exc:
        # Not retryable: same input would fail validation identically again.
        logger.error(f"Report generation validation failed for client {client_id}: {exc}")
        raise
    except LLMUnavailableError as exc:
        logger.error(f"LLM unavailable during report generation for client {client_id}: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
    except Exception as exc:
        logger.error(f"Error generating report for client {client_id}: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def sync_integration_data(self, client_id: str, integration_id: str):
    """
    Syncs data from external platforms (GA4, GSC), normalizes it,
    stores in Knowledge Base, and triggers Intelligence Layer.
    """
    logger.info(f"Starting sync for integration {integration_id} (client {client_id})")

    db = SessionLocal()
    sync_record = None
    try:
        integration = db.query(Integration).filter(Integration.id == integration_id, Integration.client_id == client_id).first()
        if not integration:
            logger.error("Integration not found")
            return {"status": "error", "message": "Integration not found"}

        sync_record = IntegrationSync(
            integration_id=integration.id,
            client_id=integration.client_id,
            status="running"
        )
        db.add(sync_record)
        db.commit()

        # 1. Connect and Sync
        connector = get_connector(integration.provider, integration.client_id, integration.id, db)
        raw_data = connector.sync()

        # 2. Normalize
        normalized_data = connector.normalize(raw_data)

        # 3. Store Normalized Data - idempotent on (integration_id, metric_type, timestamp,
        #    dimension_1, dimension_2): re-running a sync (double-click, retry, overlapping
        #    schedule) updates the existing row's values instead of inserting a duplicate.
        #    (No DB-level unique constraint exists yet for this - see docs/CLAUDE_CODE_AUDIT.md
        #    Step 2 migrations; this is the application-level guard in the meantime.)
        records = []
        for n_data in normalized_data:
            existing = db.query(NormalizedMetric).filter(
                NormalizedMetric.integration_id == integration.id,
                NormalizedMetric.metric_type == n_data.get("metric_type"),
                NormalizedMetric.timestamp == n_data.get("timestamp"),
                NormalizedMetric.dimension_1 == n_data.get("dimension_1"),
                NormalizedMetric.dimension_2 == n_data.get("dimension_2"),
            ).first()
            if existing:
                for key in ("value_1", "value_2", "value_3", "value_4", "raw_data"):
                    if key in n_data:
                        setattr(existing, key, n_data[key])
                records.append(existing)
            else:
                metric = NormalizedMetric(**n_data)
                records.append(metric)
                db.add(metric)

        sync_record.records_processed = len(records)

        # 4. Knowledge Ingestion
        _ingest_to_knowledge_layer(client_id, integration.provider, normalized_data, db)

        # 5. Intelligence Enrichment - real deterministic Rule Engine evaluation
        _trigger_intelligence_layer(client_id, integration.provider, normalized_data, db)

        sync_record.status = "success"
        sync_record.completed_at = datetime.datetime.utcnow()
        db.commit()

        _log_connector_event(db, sync_record.id, integration.client_id, "info",
                              f"Sync completed: {len(records)} records processed.")

        return {"status": "success", "processed": len(records)}
    except Exception as exc:
        if sync_record:
            sync_record.status = "failed"
            sync_record.error_message = str(exc)
            sync_record.completed_at = datetime.datetime.utcnow()
            db.commit()
            _log_connector_event(db, sync_record.id, sync_record.client_id, "error", str(exc))
        logger.error(f"Error syncing integration {integration_id}: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
    finally:
        db.close()


def _log_connector_event(db, sync_id, client_id, level: str, message: str, metadata: dict = None):
    db.add(ConnectorLog(sync_id=sync_id, client_id=client_id, level=level, message=message,
                         metadata_json=metadata))
    db.commit()


STALE_SYNC_THRESHOLD_MINUTES = 30


def reconcile_stale_syncs(db=None):
    """Marks any IntegrationSync stuck in 'running' past STALE_SYNC_THRESHOLD_MINUTES as
    'failed' - closes the gap where a worker crash mid-sync (see task_reject_on_worker_lost
    in celery_app.py) leaves the DB row orphaned forever with no terminal status. Intended
    to run on a schedule (see celery_app.py beat_schedule) or be invoked manually."""
    owns_session = db is None
    if owns_session:
        db = SessionLocal()
    try:
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(minutes=STALE_SYNC_THRESHOLD_MINUTES)
        stale = db.query(IntegrationSync).filter(
            IntegrationSync.status == "running",
            IntegrationSync.started_at < cutoff,
        ).all()
        for sync in stale:
            sync.status = "failed"
            sync.error_message = f"Reconciled: no completion recorded within {STALE_SYNC_THRESHOLD_MINUTES} minutes (likely a crashed worker)."
            sync.completed_at = datetime.datetime.utcnow()
            db.add(sync)
            _log_connector_event(db, sync.id, sync.client_id, "warning", sync.error_message)
        db.commit()
        return len(stale)
    finally:
        if owns_session:
            db.close()


@celery_app.task
def reconcile_stale_syncs_task():
    return reconcile_stale_syncs()


def _ingest_to_knowledge_layer(client_id: str, provider: str, normalized_data: list, db):
    """Creates a Knowledge Document (+ version + metadata) from normalized metrics."""
    import hashlib
    from api.models.knowledge import Document, DocumentVersion, KnowledgeMetadata

    content_text = f"Ingested {len(normalized_data)} records from {provider}."
    checksum = hashlib.sha256(content_text.encode("utf-8")).hexdigest()

    document = Document(
        client_id=uuid.UUID(client_id) if isinstance(client_id, str) else client_id,
        title=f"{provider.upper()} Data Sync — {datetime.datetime.utcnow().date().isoformat()}",
        source_type="integration_sync",
        mime_type="text/plain",
        file_size=len(content_text.encode("utf-8")),
        checksum=checksum,
        status="completed",
    )
    db.add(document)
    db.flush()

    version = DocumentVersion(
        document_id=document.id,
        version=1,
        raw_text=content_text,
        processing_status="completed",
    )
    db.add(version)

    metadata = KnowledgeMetadata(
        document_id=document.id,
        tags=["integration", provider],
        custom_metadata={
            "type": "integration_sync",
            "provider": provider,
            "record_count": len(normalized_data),
        },
    )
    db.add(metadata)
    db.commit()
    logger.info(f"Ingested sync data into Knowledge Base for {client_id}")
    return document


GA4_FIELD_MAP = {"value_1": "sessions", "value_2": "conversions", "value_3": "revenue", "value_4": "bounce_rate"}
GSC_FIELD_MAP = {"value_1": "clicks", "value_2": "impressions", "value_3": "ctr", "value_4": "position"}
PROVIDER_FIELD_MAPS = {"ga4": GA4_FIELD_MAP, "gsc": GSC_FIELD_MAP}


def _aggregate_metrics_for_provider(provider: str, normalized_data: list) -> dict:
    """Averages each provider's generic value_1..4 fields across all rows in this sync
    and relabels them with their real semantic name, so the Rule Engine's deterministic
    checks (which key off named metrics like 'ctr'/'bounce_rate') can actually run
    against them - the NormalizedMetric schema is intentionally generic, but the Rule
    Engine needs to know what value_3 means for THIS provider."""
    field_map = PROVIDER_FIELD_MAPS.get(provider, {})
    if not field_map or not normalized_data:
        return {}

    sums, counts = {}, {}
    for row in normalized_data:
        for raw_key, semantic_key in field_map.items():
            value = row.get(raw_key)
            if value is None:
                continue
            sums[semantic_key] = sums.get(semantic_key, 0) + value
            counts[semantic_key] = counts.get(semantic_key, 0) + 1

    return {k: sums[k] / counts[k] for k in sums}


def _trigger_intelligence_layer(client_id: str, provider: str, normalized_data: list, db):
    """Runs the real, deterministic Rule Engine over this sync's metrics and records any
    signals found as a ConnectorLog entry. No historical comparison yet (would need a
    prior-sync lookup) - this only evaluates the current-period threshold rules, which is
    a real, honest subset of the Intelligence Layer, not a full trend analysis."""
    from api.services.intelligence.rule_engine import RuleEngine

    current_metrics = _aggregate_metrics_for_provider(provider, normalized_data)
    if not current_metrics:
        logger.info(f"No mappable metrics for provider {provider}; skipping Intelligence Layer evaluation.")
        return

    signals = RuleEngine().evaluate_metrics(current_metrics)
    logger.info(f"Intelligence Layer produced {len(signals)} signal(s) for {client_id} on {provider} data")

    if signals:
        client_uuid = uuid.UUID(client_id) if isinstance(client_id, str) else client_id
        db.add(ConnectorLog(
            sync_id=None, client_id=client_uuid, level="info",
            message=f"Intelligence Layer found {len(signals)} signal(s) for {provider} sync.",
            metadata_json={"signals": signals},
        ))
        db.commit()
