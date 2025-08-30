from celery import Celery
from infonomy_server.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

# Force Redis transport by modifying the URLs if they don't already specify it
broker_url = CELERY_BROKER_URL if '://' in CELERY_BROKER_URL else f"redis://{CELERY_BROKER_URL}"
backend_url = CELERY_RESULT_BACKEND if '://' in CELERY_RESULT_BACKEND else f"redis://{CELERY_RESULT_BACKEND}"

# Use configuration from config.py and explicitly specify Redis transport
celery = Celery(
    "infonomy_server",
    broker=broker_url,
    backend=backend_url,
    include=['infonomy_server.tasks']
)

# Configure Celery to use Redis transport explicitly - more aggressive approach
celery.conf.update(
    # Force Redis transport
    broker_transport='redis',
    result_backend_transport='redis',
    
    # Override any default broker settings
    broker_url=broker_url,
    result_backend=backend_url,
    
    # Redis-specific configuration
    broker_transport_options={
        'visibility_timeout': 3600,
        'fanout_prefix': True,
        'fanout_patterns': True,
        'socket_connect_timeout': 5,
        'socket_timeout': 5,
        'retry_on_timeout': True,
    },
    redis_backend_use_ssl=False,
    redis_broker_use_ssl=False,
    
    # Task configuration
    result_expires=3600,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Disable AMQP transport
    broker_transport_shortnames={
        'redis': 'redis',
        'amqp': 'redis',  # Force AMQP to use Redis
    }
)

# Set this as the current Celery app so shared_task decorators use it
celery.set_current()

# just import your tasks module so Celery sees them:
import infonomy_server.tasks  # noqa: F401