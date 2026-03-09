"""
Celery application configuration for Product Intelligence Platform.
"""

from celery import Celery

from app.config import settings

# Create Celery application
celery_app = Celery(
    "product_intelligence_platform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.worker.tasks"],
)

# Configure Celery
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution settings
    task_soft_time_limit=3600,  # 1 hour
    task_time_limit=4000,  # ~1.1 hours
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # Result backend settings
    result_expires=3600,  # 1 hour
    result_persistent=True,

    # Beat schedule (for future use)
    beat_schedule={},
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.worker"])
