from django.shortcuts import render, get_object_or_404
from .models import Event, EventCategory
from . import selectors

# Create your views here.
def event_list(request):
    filter_type = request.GET.get('filter', 'upcoming')  # default to upcoming
    if filter_type == 'past':
        events = selectors.get_past_events()
    elif filter_type == 'ongoing':
        events = selectors.get_ongoing_events()
    else:
        events = selectors.get_upcoming_events()
        filter_type = 'upcoming'  # ensure it's set

    # Get all categories for the filter dropdown (if you still want category filter)
    categories = EventCategory.objects.all()

    context = {
        'events': events,
        'filter': filter_type,
        'categories': categories,
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