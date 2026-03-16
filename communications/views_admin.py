from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .models import Subscriber
from community.models import Patron
from core.services.webhooks import send_webhook

@staff_member_required
def send_custom_message(request):
    if request.method == 'POST':
        # Get selected IDs from form
        subscriber_ids = request.POST.getlist('subscribers')
        patron_ids = request.POST.getlist('patrons')
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()

        # Collect emails
        emails = []
        if subscriber_ids:
            emails.extend(Subscriber.objects.filter(
                id__in=subscriber_ids, is_active=True
            ).values_list('email', flat=True))
        if patron_ids:
            emails.extend(Patron.objects.filter(
                id__in=patron_ids, is_active=True
            ).exclude(email='').values_list('email', flat=True))

        if not emails:
            messages.error(request, "No valid recipients selected.")
        elif not subject or not body:
            messages.error(request, "Subject and body are required.")
        else:
            payload = {
                'recipients': list(emails),
                'subject': subject,
                'body': body,
            }
            send_webhook('admin_message', payload)
            messages.success(request, f"Message sent to {len(emails)} recipient(s).")

        return redirect('admin:communications_subscriber_changelist')

    # GET: display form, with pre-selected subscribers from session
    selected_ids = request.session.pop('selected_subscriber_ids', [])
    subscribers = Subscriber.objects.filter(is_active=True).order_by('email')
    patrons = Patron.objects.filter(is_active=True).exclude(email='').order_by('name')
    return render(request, 'admin/communications/send_custom_message.html', {
        'subscribers': subscribers,
        'patrons': patrons,
        'selected_subscriber_ids': selected_ids,
    })