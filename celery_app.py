from celery import Celery

# you can use Redis, RabbitMQ, etc. 
# Here we’ll assume Redis on localhost for both broker & result backend:
celery = Celery(
    "qa_platform",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

# Optional: auto-discover tasks in this module
celery.autodiscover_tasks(["tasks"])
