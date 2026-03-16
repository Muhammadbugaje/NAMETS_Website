from django.utils import timezone
from django.db.models import Q
from .models import Event

def get_upcoming_events():
    """Return events that start in the future."""
    return Event.objects.filter(
        start_datetime__gte=timezone.now(),
        is_active=True
    ).order_by('start_datetime')

def get_ongoing_events():
    """Return events currently happening."""
    now = timezone.now()
    return Event.objects.filter(
        start_datetime__lte=now,
        end_datetime__gte=now,
        is_active=True
    ).order_by('start_datetime')

def get_past_events():
    """Return events that have ended."""
    return Event.objects.filter(
        end_datetime__lt=timezone.now(),
        is_active=True
    ).order_by('-end_datetime')

def get_featured_events():
    """Return featured upcoming/ongoing events."""
    now = timezone.now()
    return Event.objects.filter(
        is_featured=True,
        is_active=True,
        end_datetime__gte=now  # not past
    ).order_by('start_datetime')

def get_events_by_category(category_slug):
    """Return active events for a given category slug."""
    return Event.objects.filter(
        category__slug=category_slug,
        is_active=True
    ).order_by('start_datetime')