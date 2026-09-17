"""
Direct Brevo email engine with HTML template support — replaces the n8n webhook integration.

Every notification that used to call core.services.webhooks.send_webhook()
now calls send_mail() here directly. Sends over Brevo's HTTPS API.

Supports Django template rendering for HTML emails with NAMETS branding.
Now logs every email attempt to EmailLog for tracking.
"""

import logging
import requests
from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import send_mail as django_send_mail, get_connection
from django.utils import timezone

# Import models for logging
from .models import EmailLog, DailyEmailCounter

logger = logging.getLogger(__name__)

# ===== NEW: Daily limits =====
BREVO_DAILY_LIMIT = 300
GMAIL_DAILY_LIMIT = 500
CRITICAL_CATEGORIES = {'credentials', 'reset', 'task', 'voting', 'unsubscribe'}


# core/email_utils.py

def get_logo_url():
    """
    Get the logo URL with a fallback.
    If the primary URL fails, use a backup URL.
    """
    # Primary URL from settings (your .env file)
    primary_url = getattr(settings, 'LOGO_URL', None)
    
    # Backup URL (hardcoded as a safety net)
    fallback_url = 'https://res.cloudinary.com/dgkin4erd/image/upload/v1788637376/Namets_oaapzr.jpg'
    
    # If no primary URL is set, use the fallback
    if not primary_url:
        return fallback_url
    
    # Check if the primary URL is valid (optional but recommended)
    try:
        import requests
        response = requests.head(primary_url, timeout=3)
        if response.status_code == 200:
            return primary_url
    except:
        # If the primary URL fails, use the fallback
        return fallback_url
    
    return fallback_url


def render_email_template(template_name, context):
    """
    Render an HTML email template with NAMETS branding.
    
    template_name: the template path (e.g., 'emails/announcement.html')
    context: dict of template variables
    """
    base_context = {
        'logo_url': get_logo_url(),
        'site_url': getattr(settings, 'SITE_URL', 'https://namets.org'),
        'unsubscribe_url': getattr(settings, 'UNSUBSCRIBE_URL', 'https://namets.org/communications/unsubscribe/'),
    }
    base_context.update(context)
    return render_to_string(template_name, base_context)


# ===== NEW: Brevo send helper =====
def _send_via_brevo(subject, recipients, html_message, text_message, category):
    """Send via Brevo API (your existing code, extracted)."""
    api_key = getattr(settings, 'BREVO_API_KEY', None)
    if not api_key:
        raise Exception("BREVO_API_KEY not configured")

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'NAMETS <no-reply@namets.org>')
    sender_email = from_email.split('<')[-1].rstrip('>') if '<' in from_email else from_email

    payload = {
        'sender': {'name': 'NAMETS', 'email': sender_email},
        'to': [{'email': email} for email in recipients],
        'subject': subject,
        'htmlContent': html_message,
        'textContent': text_message or html_message,
    }

    response = requests.post(
        'https://api.brevo.com/v3/smtp/email',
        headers={
            'api-key': api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
        json=payload,
        timeout=10,
    )
    if response.status_code not in (200, 201):
        raise Exception(f"Brevo API error {response.status_code}: {response.text[:200]}")
    return True


# ===== NEW: Gmail send helper =====
def _send_via_gmail(subject, recipients, html_message, text_message, category):
    """Send via Gmail SMTP."""
    connection = get_connection(
        backend='django.core.mail.backends.smtp.EmailBackend',
        host='smtp.gmail.com',
        port=587,
        username=getattr(settings, 'GMAIL_EMAIL_USER', None),
        password=getattr(settings, 'GMAIL_APP_PASSWORD', None),
        use_tls=True,
    )
    if not connection.username or not connection.password:
        raise Exception("Gmail credentials not configured")
    return django_send_mail(
        subject,
        text_message or html_message,
        getattr(settings, 'DEFAULT_FROM_EMAIL', 'NAMETS <namets.notifications@gmail.com>'),
        recipients,
        html_message=html_message,
        connection=connection
    ) > 0


# ===== NEW: Fallback email sender (the new main function) =====
def send_email_with_fallback(subject, message, recipient_list, html_message=None, category='general'):
    """
    Send email with Brevo → Gmail fallback.
    Returns True if at least one recipient received the email.
    
    - Critical emails (credentials, reset, task, voting, unsubscribe): Brevo first
    - Bulk/general emails: Gmail first (saves Brevo quota)
    """
    if not recipient_list:
        return False

    # Get today's counter
    counter, _ = DailyEmailCounter.objects.get_or_create(date=timezone.now().date())

    # Determine order
    critical = category in CRITICAL_CATEGORIES
    order = ['brevo', 'gmail'] if critical else ['gmail', 'brevo']

    success_count = 0

    for provider in order:
        # Check daily limit
        if provider == 'brevo' and counter.brevo_count >= BREVO_DAILY_LIMIT:
            logger.warning("Brevo daily limit (%s) reached. Switching to Gmail.", BREVO_DAILY_LIMIT)
            continue
        if provider == 'gmail' and counter.gmail_count >= GMAIL_DAILY_LIMIT:
            logger.warning("Gmail daily limit (%s) reached.", GMAIL_DAILY_LIMIT)
            continue

        try:
            if provider == 'brevo':
                _send_via_brevo(subject, recipient_list, html_message or message, message, category)
            else:
                _send_via_gmail(subject, recipient_list, html_message or message, message, category)

            # Success — update counter and log
            if provider == 'brevo':
                counter.brevo_count += 1
            else:
                counter.gmail_count += 1
            counter.save()

            for email in recipient_list:
                EmailLog.objects.create(
                    recipient_email=email,
                    subject=subject,
                    category=category,
                    provider=provider.capitalize(),
                    status='sent',
                )

            success_count += len(recipient_list)
            logger.info("Email sent to %d recipient(s) via %s: %s", len(recipient_list), provider, subject)
            return True

        except Exception as e:
            # Log failure for this provider
            error_msg = str(e)[:500]
            logger.error("Email failed via %s: %s", provider, error_msg)
            for email in recipient_list:
                EmailLog.objects.create(
                    recipient_email=email,
                    subject=subject,
                    category=category,
                    provider=provider.capitalize(),
                    status='failed',
                    error_message=error_msg,
                )
            continue

    # Both providers exhausted or failed
    for email in recipient_list:
        EmailLog.objects.create(
            recipient_email=email,
            subject=subject,
            category=category,
            provider='failed',
            status='failed',
            error_message='Both providers exhausted or failed',
        )
    return False


# ===== MODIFIED: send_mail now uses fallback =====
def send_mail(subject, recipients, html_message=None, text_message=None, 
              template_name=None, context=None, category='general'):
    """
    Send an email via Brevo's API with full logging.
    
    Now uses the fallback system (Brevo → Gmail).
    
    Returns True if Brevo accepted the send, False otherwise.
    Logs every attempt (success or failure) to EmailLog.
    """
    # If template provided, render it
    if template_name and context is not None:
        html_message = render_email_template(template_name, context)

    if not html_message:
        logger.error("No HTML content provided for email: %s", subject)
        for email in recipients:
            EmailLog.objects.create(
                recipient_email=email,
                subject=subject,
                category=category,
                provider='failed',
                status='failed',
                error_message='No HTML content provided',
            )
        return False

    # Use the new fallback system
    return send_email_with_fallback(
        subject=subject,
        message=text_message or html_message,
        recipient_list=recipients,
        html_message=html_message,
        category=category,
    )


# ===== UNCHANGED: send_templated_email (now uses send_mail with fallback) =====
def send_templated_email(subject, recipients, template_name, context, text_message=None, category='general'):
    """
    Convenience function to send a templated email with logging.
    """
    return send_mail(
        subject=subject,
        recipients=recipients,
        template_name=template_name,
        context=context,
        text_message=text_message,
        category=category,
    )