import os
from celery import Celery

# Set default Django settings
os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE',
    'PlacementReady.settings'
)

# Create celery app
app = Celery('PlacementReady')

# Load celery settings from Django settings
app.config_from_object(
    'django.conf:settings',
    namespace='CELERY'
)

# Auto-discover tasks
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')