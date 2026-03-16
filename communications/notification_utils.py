from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

def send_notification_email(subject, template_name, context, recipient_list):
    """Generic email sender. For now uses Django's email backend."""
    html_message = render_to_string(template_name, context)
    send_mail(
        subject,
        '',
        settings.DEFAULT_FROM_EMAIL,
        recipient_list,
        html_message=html_message,
        fail_silently=False,
    )