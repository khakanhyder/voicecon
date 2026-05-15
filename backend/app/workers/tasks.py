"""Background tasks."""
from app.workers.celery_app import app
import logging

logger = logging.getLogger(__name__)


@app.task
def health_check():
    """Simple health check task."""
    return {"status": "ok"}
