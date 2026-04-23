from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "medquest_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.pipeline"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_routes={
        "app.workers.pipeline.*": {"queue": "medquest_queue"}
    }
)
