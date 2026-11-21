"""
Django email backend that sends through Brevo's HTTP API (HTTPS, port 443),
so it works on hosts that block SMTP ports (e.g. Render free tier).
Existing send_mail(...) / EmailMessage calls keep working unchanged.
"""
import logging
import os
from email.utils import parseaddr

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


class BrevoEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, api_key=None, **kwargs):
        # Django 6.1 rejects unknown options in BaseEmailBackend.__init__,
        # so fail_silently is handled here instead of being passed up.
        super().__init__(**kwargs)
        self.fail_silently = fail_silently
        self.api_key = (
            api_key
            or getattr(settings, "BREVO_API_KEY", None)
            or os.environ.get("BREVO_API_KEY")
        )

    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            try:
                self._send(message)
                sent += 1
            except Exception:
                logger.exception("Brevo send failed for subject '%s'", message.subject)
                if not self.fail_silently:
                    raise
        return sent

    def _send(self, message):
        if not self.api_key:
            raise RuntimeError("BREVO_API_KEY is not configured.")

        name, addr = parseaddr(message.from_email or settings.DEFAULT_FROM_EMAIL)
        payload = {
            "sender": {"email": addr, **({"name": name} if name else {})},
            "to": [{"email": parseaddr(r)[1]} for r in message.to],
            "subject": message.subject,
        }
        if message.cc:
            payload["cc"] = [{"email": parseaddr(r)[1]} for r in message.cc]

        html = None
        for content, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                html = content
        if html:
            payload["htmlContent"] = html
            payload["textContent"] = message.body
        elif message.content_subtype == "html":
            payload["htmlContent"] = message.body
        else:
            payload["textContent"] = message.body

        resp = requests.post(
            BREVO_URL,
            json=payload,
            headers={"api-key": self.api_key, "accept": "application/json"},
            timeout=15,
        )
        if resp.status_code >= 400:
            # Include Brevo's response body so the real reason shows up in the logs
            raise RuntimeError(f"Brevo API error {resp.status_code}: {resp.text}")