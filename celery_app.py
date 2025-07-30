from celery import Celery


# you can use Redis, RabbitMQ, etc. 
# Here we’ll assume Redis on localhost for both broker & result backend:
celery = Celery(
    "infonomy_server",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

# instead of autodiscover:
# celery.autodiscover_tasks(["tasks"])

# just import your tasks module so Celery sees them:
import infonomy_server.tasks  # noqa: F401