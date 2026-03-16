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
            # Get checkbox values (they are Booleans)
            notify_announcements = form.cleaned_data.get('notify_announcements', False)
            notify_events = form.cleaned_data.get('notify_events', False)
            notify_prayer_changes = form.cleaned_data.get('notify_prayer_changes', False)

            subscriber, created = Subscriber.objects.get_or_create(
                email=email,
                defaults={
                    'notify_announcements': notify_announcements,
                    'notify_events': notify_events,
                    'notify_prayer_changes': notify_prayer_changes,
                }
            )
            if not created:
                # Update preferences
                subscriber.notify_announcements = notify_announcements
                subscriber.notify_events = notify_events
                subscriber.notify_prayer_changes = notify_prayer_changes
                subscriber.is_active = True
                subscriber.save()
                messages.success(request, 'Your subscription preferences have been updated.')
            else:
                messages.success(request, 'Thank you for subscribing! Please check your email to confirm')
            return redirect('core:homepage')
        else:
            # If form invalid, show errors (you might want to handle gracefully)
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            return redirect('core:homepage')
    else:
        # If GET request, maybe show a page? But we're using it only via POST from homepage.
        return redirect('core:homepage')

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
