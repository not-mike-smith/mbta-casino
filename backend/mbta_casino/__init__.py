# Import the Celery app so it is initialised when Django starts.
# This ensures @shared_task decorators in tasks.py bind to this app.
from .celery import app as celery_app

__all__ = ["celery_app"]
