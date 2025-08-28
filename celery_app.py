from celery import Celery
from infonomy_server.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

# Use configuration from config.py and explicitly specify Redis transport
celery = Celery(
    "infonomy_server",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=['infonomy_server.tasks']
)

# Configure Celery to use Redis transport explicitly
celery.conf.update(
    broker_transport='redis',
    result_backend_transport='redis',
    broker_transport_options={
        'visibility_timeout': 3600,
        'fanout_prefix': True,
        'fanout_patterns': True,
    },
    result_expires=3600,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# Set this as the current Celery app so shared_task decorators use it
celery.set_current()

# just import your tasks module so Celery sees them:
import infonomy_server.tasks  # noqa: F401