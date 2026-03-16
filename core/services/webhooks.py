import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

def send_webhook(event_type, data):
    url = settings.N8N_WEBHOOK_URL
    if not url:
        logger.error("N8N_WEBHOOK_URL not set")
        return

    # Include token in the payload
    payload = {
        'event': event_type,
        # 'token': settings.WEBHOOK_SECRET,   # ← your hardcoded token
        'data': data,
    }

    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        logger.info(f"Webhook sent: {event_type}")
    except Exception as e:
        logger.error(f"Webhook failed for {event_type}: {e}")