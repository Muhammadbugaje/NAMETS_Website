from django.shortcuts import render, get_object_or_404
from .models import Event, EventCategory
from . import selectors
from django.http import HttpResponse
from icalendar import Calendar, Event as ICalEvent
from django.utils import timezone
from django.shortcuts import render
from .models import Event, EventCategory
from . import selectors
# Create your views here.

def event_list(request):
    # Get filter type from URL (upcoming/ongoing/past)
    filter_type = request.GET.get('filter', 'upcoming')
    # Get category slug from URL
    category_slug = request.GET.get('category')

    # Start with base queryset based on filter
    if filter_type == 'past':
        events = selectors.get_past_events()
    elif filter_type == 'ongoing':
        events = selectors.get_ongoing_events()
    else:
        events = selectors.get_upcoming_events()
        filter_type = 'upcoming'  # ensure

    # Apply category filter if provided
    if category_slug:
        events = events.filter(category__slug=category_slug)

    # Get all categories for the dropdown
    categories = EventCategory.objects.all()

    context = {
        'events': events,
        'filter': filter_type,
        'categories': categories,
        'selected_category': category_slug,
    }
    return render(request, 'events/event_list.html', context)

def event_detail(request, slug):
    event = get_object_or_404(Event, slug=slug, is_active=True)
    context = {
        'event': event,
    }
    return render(request, 'events/event_detail.html', context)

def upcoming_events(request):
    events = selectors.get_upcoming_events()
    context = {'events': events}
    return render(request, 'events/upcoming.html', context)

def past_events(request):
    events = selectors.get_past_events()
    context = {'events': events}
    return render(request, 'events/past.html', context)

def calendar_ics(request, slug):
    event = get_object_or_404(Event, slug=slug, is_active=True)

    cal = Calendar()
    cal.add('prodid', '-//NAMETS//Event//EN')
    cal.add('version', '2.0')

    ical_event = ICalEvent()
    ical_event.add('summary', event.title)
    ical_event.add('dtstart', event.start_datetime)
    ical_event.add('dtend', event.end_datetime)
    ical_event.add('location', event.location or 'TBA')
    ical_event.add('description', event.description)
    ical_event.add('uid', f'event-{event.id}@namets.org')
    ical_event.add('dtstamp', timezone.now())

    cal.add_component(ical_event)

    response = HttpResponse(cal.to_ical(), content_type='text/calendar')
    response['Content-Disposition'] = f'attachment; filename="{event.slug}.ics"'
    return response