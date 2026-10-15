import os
from celery import Celery
# Importing api.core.config (rather than reading os.environ directly here) guarantees
# .env is loaded before these values are read, regardless of which module happens to
# import this file first - see the load_dotenv() call at the top of config.py.
from api.core.config import settings

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "deepinsight_tasks",
    broker=os.environ.get("CELERY_BROKER_URL", REDIS_URL),
    backend=os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL),
    include=["api.core.tasks"],
)

# IMPORTANT: task_routes keys must match the actual registered task name
# (module_path.function_name), not a made-up namespace - a mismatch here means
# dispatched tasks silently land in Celery's default "celery" queue, which the worker
# (docker-compose.yml: `-Q default,heavy_processing`) never consumes, so they'd hang
# forever. See docs/CLAUDE_CODE_AUDIT.md.
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue="default",  # anything not explicitly routed below still lands
                                    # on a queue the worker actually consumes.
    task_routes={
        "api.core.tasks.process_report_generation": {"queue": "heavy_processing"},
        "api.core.tasks.process_content_generation": {"queue": "heavy_processing"},
        "api.core.tasks.process_seo_analysis": {"queue": "heavy_processing"},
        "api.core.tasks.sync_integration_data": {"queue": "default"},
    },
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Dev/demo mode only: runs tasks synchronously in-process, no Redis/worker needed.
    # CELERY_EAGER=true is meant for local development without live infrastructure -
    # docker-compose.yml never sets it, so a real deployment always dispatches for
    # real. task_eager_propagates makes .delay() actually raise the task's exception
    # inline (instead of swallowing it), matching what a caller would expect when the
    # task ran synchronously in their own request.
    task_always_eager=settings.CELERY_EAGER,
    task_eager_propagates=True,
    beat_schedule={
        # Closes IntegrationSync rows orphaned "running" by a crashed/killed worker -
        # requires a `celery beat` process running alongside the worker.
        "reconcile-stale-integration-syncs": {
            "task": "api.core.tasks.reconcile_stale_syncs_task",
            "schedule": 600.0,  # every 10 minutes
        },
    },
)
