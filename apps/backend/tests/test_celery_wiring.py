import datetime
import uuid
from unittest.mock import MagicMock, patch

from api.core.celery_app import celery_app
from api.core.tasks import (
    _aggregate_metrics_for_provider, _trigger_intelligence_layer, reconcile_stale_syncs,
    STALE_SYNC_THRESHOLD_MINUTES,
)


def test_task_routes_reference_real_registered_task_names():
    """Regression guard for the exact bug the audit found: task_routes keys that don't
    match any real task name mean dispatched work silently lands in an unconsumed queue."""
    registered_task_names = set(celery_app.tasks.keys())
    for routed_name in celery_app.conf.task_routes:
        assert routed_name in registered_task_names, (
            f"'{routed_name}' in task_routes does not match any registered Celery task "
            f"- it would route to nowhere. Registered: {sorted(n for n in registered_task_names if n.startswith('api.'))}"
        )


def test_default_queue_is_one_the_worker_actually_consumes():
    # docker-compose.yml's celery_worker runs `-Q default,heavy_processing`
    assert celery_app.conf.task_default_queue in {"default", "heavy_processing"}


def test_report_and_content_generation_route_to_heavy_processing():
    assert celery_app.conf.task_routes["api.core.tasks.process_report_generation"]["queue"] == "heavy_processing"
    assert celery_app.conf.task_routes["api.core.tasks.process_content_generation"]["queue"] == "heavy_processing"


def test_seo_analysis_routes_to_heavy_processing():
    assert celery_app.conf.task_routes["api.core.tasks.process_seo_analysis"]["queue"] == "heavy_processing"


def test_ga4_metric_aggregation_maps_generic_fields_to_semantic_names():
    normalized = [
        {"value_1": 100, "value_2": 10, "value_3": 500.0, "value_4": 0.5},
        {"value_1": 200, "value_2": 20, "value_3": 700.0, "value_4": 0.3},
    ]
    result = _aggregate_metrics_for_provider("ga4", normalized)
    assert result["sessions"] == 150
    assert result["bounce_rate"] == 0.4


def test_unknown_provider_returns_empty_aggregation():
    assert _aggregate_metrics_for_provider("unknown_provider", [{"value_1": 1}]) == {}


def test_trigger_intelligence_layer_no_signal_when_no_rule_matches():
    db = MagicMock()
    # ga4 never produces "ctr" (see GA4_FIELD_MAP), so the Web rule (needs ctr+bounce_rate) can't fire.
    normalized_ga4 = [{"value_1": 1000, "value_4": 0.1}]  # sessions=1000, bounce_rate=0.1
    _trigger_intelligence_layer(str(uuid.uuid4()), "ga4", normalized_ga4, db)
    db.add.assert_not_called()


def test_trigger_intelligence_layer_logs_signal_when_rule_matches():
    db = MagicMock()
    # gsc: ctr(value_3)=0.05 > 0.03 - only half of the Web rule's pair, but GSC alone
    # can still trigger a rule that only needs one of its mapped fields to cross a
    # threshold. Use metrics that are guaranteed to match a real rule instead of
    # guessing: open_rate/click_rate aren't gsc/ga4 fields at all, so assert on the
    # generic contract (ConnectorLog written) via a synthetic aggregation instead.
    with patch("api.core.tasks._aggregate_metrics_for_provider", return_value={"ctr": 0.2, "bounce_rate": 0.05}):
        _trigger_intelligence_layer(str(uuid.uuid4()), "gsc", [{"value_3": 0.2}], db)
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_reconcile_stale_syncs_marks_old_running_syncs_failed(db_maker=None):
    from api.models.integrations import IntegrationSync

    old_sync = MagicMock(spec=IntegrationSync)
    old_sync.status = "running"
    old_sync.started_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=STALE_SYNC_THRESHOLD_MINUTES + 5)
    old_sync.id = uuid.uuid4()
    old_sync.client_id = uuid.uuid4()

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [old_sync]

    count = reconcile_stale_syncs(db=db)

    assert count == 1
    assert old_sync.status == "failed"
    assert old_sync.completed_at is not None
    db.commit.assert_called()
