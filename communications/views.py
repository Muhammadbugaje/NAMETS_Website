from django.shortcuts import redirect, render, get_object_or_404
from .models import Announcement, PrayerSchedule, DonationCampaign
from . import selectors
# imports for subscription stuff 
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from .forms import SubscriptionForm
from .models import Subscriber
import uuid
from core.services.webhooks import send_webhook
# Create your views here.

def announcement_list(request):
    announcements = selectors.get_active_announcements()
    context = {
        'announcements': announcements,
    }
    return render(request, 'communications/announcement_list.html', context)

def announcement_detail(request, slug):
    announcement = get_object_or_404(Announcement, slug=slug, is_active=True)
    context = {
        'announcement': announcement,
    }
    return render(request, 'communications/announcement_detail.html', context)

def prayer_times(request):
    schedule = selectors.get_today_prayer_schedule()
    context = {
        'schedule': schedule,
    }
    return render(request, 'communications/prayer_times.html', context)


def donation_list(request):
    campaigns = selectors.get_active_donation_campaigns()
    return render(request, 'communications/donation_list.html', {'campaigns': campaigns})

def mosque_info(request):
    info = selectors.get_mosque_info()
    rules = selectors.get_active_mosque_rules()
    context = {
        'info': info,
        'rules': rules,
    }
    return render(request, 'communications/mosque_info.html', context)


def subscribe(request):
    if request.method == 'POST':
        form = SubscriptionForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            new_prefs = {
                'notify_announcements': form.cleaned_data.get('notify_announcements', False),
                'notify_events': form.cleaned_data.get('notify_events', False),
                'notify_prayer_changes': form.cleaned_data.get('notify_prayer_changes', False),
            }

            try:
                subscriber = Subscriber.objects.get(email=email)
                current_prefs = {
                    'notify_announcements': subscriber.notify_announcements,
                    'notify_events': subscriber.notify_events,
                    'notify_prayer_changes': subscriber.notify_prayer_changes,
                }

                if current_prefs != new_prefs:
                    # Store in session and redirect to confirm page
                    request.session['pending_subscription'] = {
                        'email': email,
                        'new_prefs': new_prefs,
                        'current_prefs': current_prefs,
                    }
                    request.session.modified = True
                    return redirect('communications:confirm_subscription')
                else:
                    messages.info(request, "You're already subscribed with these preferences.")
                    return redirect('core:homepage')

            except Subscriber.DoesNotExist:
                # New subscriber
                Subscriber.objects.create(
                    email=email,
                    token=uuid.uuid4(),
                    is_verified=False,
                    is_active=True,
                    **new_prefs
                )
                messages.success(request, 'Thank you for subscribing!')
                return redirect('core:homepage')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            return redirect('core:homepage')
    else:
        return redirect('core:homepage')

def confirm_subscription(request):
    pending = request.session.get('pending_subscription')

    if not pending:
        messages.error(request, 'No pending request found. Please try again.')
        return redirect('core:homepage')

    if request.method == 'POST':
        email = pending['email']
        new_prefs = pending['new_prefs']

        try:
            subscriber = Subscriber.objects.get(email__iexact=email)
        except Subscriber.DoesNotExist:
            messages.error(request, 'Subscriber not found.')
            return redirect('core:homepage')

        subscriber.notify_announcements = new_prefs['notify_announcements']
        subscriber.notify_events = new_prefs['notify_events']
        subscriber.notify_prayer_changes = new_prefs['notify_prayer_changes']
        subscriber.save(update_fields=[
            'notify_announcements', 
            'notify_events', 
            'notify_prayer_changes'
        ])

        try:
            send_webhook('subscriber_updated', {
                'recipients': [email],
                'email': email,
                'preferences': new_prefs
            })
        except Exception:
            pass

        del request.session['pending_subscription']
        messages.success(request, 'Your preferences have been updated!')
        return redirect('core:homepage')

    return render(request, 'communications/confirm_subscription.html', {
        'email': pending['email'],
        'current_prefs': pending['current_prefs'],
        'new_prefs': pending['new_prefs'],
    })

def subscribe_success(request):
    return render(request, 'communications/subscribe_success.html')


def unsubscribe(request, token):
    subscriber = get_object_or_404(Subscriber, token=token)
    if request.method == 'POST':
        email = subscriber.email
        subscriber.delete()
        messages.success(request, f'{email} has been unsubscribed and removed from our records.')
        return redirect('core:homepage')
    return render(request, 'communications/unsubscribe_confirm.html', {'subscriber': subscriber})

def unsubscribe_by_email(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        if not email:
            messages.error(request, 'Please enter an email address.')
            return redirect('communications:unsubscribe_by_email')
        try:
            subscriber = Subscriber.objects.get(email=email)
            subscriber.delete()
            messages.success(request, f'{email} has been unsubscribed and removed from our records.')
        except Subscriber.DoesNotExist:
            messages.error(request, f'No subscription found for {email}.')
        return redirect('core:homepage')
    return render(request, 'communications/unsubscribe_by_email.html')
