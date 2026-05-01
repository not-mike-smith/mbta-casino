import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mbta_casino.settings")

app = Celery("mbta_casino")

# Pull all CELERY_* keys from Django settings into Celery config.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in each installed app's tasks.py module.
app.autodiscover_tasks()
