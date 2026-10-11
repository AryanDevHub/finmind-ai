"""celery_app.py — Celery application + beat schedule. Start with:

    celery -A backend.celery_app worker -l info --concurrency 2
    celery -A backend.celery_app beat   -l info
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from backend.settings import get_settings

_s = get_settings()

celery_app = Celery("finmind", broker=_s.redis_url, include=["backend.tasks"])
celery_app.conf.update(
    task_serializer="json", accept_content=["json"], result_serializer="json",
    task_ignore_result=True,
    task_acks_late=True,                 # re-deliver if a worker dies mid-task (tasks are idempotent)
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=4,
    task_time_limit=300, task_soft_time_limit=240,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 3600},
    timezone=_s.app_timezone, enable_utc=True,
    beat_schedule={
        # Reconciliation: picks up any row whose event was lost (publish failed, worker down).
        "embed-pending": {"task": "finmind.embed_pending", "schedule": 60.0},
        "reconcile-budgets": {"task": "finmind.reconcile_budgets", "schedule": 600.0},
        "nightly-anomalies": {"task": "finmind.nightly_anomalies", "schedule": crontab(hour=2, minute=0)},
        "nightly-forecasts": {"task": "finmind.nightly_forecasts", "schedule": crontab(hour=2, minute=30)},
        "purge-refresh-tokens": {"task": "finmind.purge_refresh_tokens", "schedule": crontab(hour=3, minute=0)},
    },
)
