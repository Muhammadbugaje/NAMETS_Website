from django.shortcuts import render, get_object_or_404
from .models import Event, EventCategory
from . import selectors
from django.http import HttpResponse
from icalendar import Calendar, Event as ICalEvent
from django.utils import timezone
from django.shortcuts import render
from .models import Event, EventCategory
from . import selectors
from django.utils.html import strip_tags


from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect
from .forms import EventForm, EventLinkFormSet


from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from google import genai
from google.genai.types import GenerateContentConfig


from django.db.models import Prefetch


def event_list(request):
    filter_type = request.GET.get('filter', 'upcoming')
    category_slug = request.GET.get('category')

    # Base queryset
    if filter_type == 'past':
        events = selectors.get_past_events()
    elif filter_type == 'ongoing':
        events = selectors.get_ongoing_events()
    else:
        events = selectors.get_upcoming_events()
        filter_type = 'upcoming'

    if category_slug:
        events = events.filter(category__slug=category_slug)

    events = events.prefetch_related('links')

    categories = EventCategory.objects.all()

    context = {
        'events': events,
        'filter': filter_type,
        'categories': categories,
        'selected_category': category_slug,
    }
    return render(request, 'events/event_list.html', context)


def event_detail(request, slug):
    event = get_object_or_404(
        Event.objects.prefetch_related('links'),
        slug=slug,
        is_active=True
    )
    return render(request, 'events/event_detail.html', {'event': event})

def upcoming_events(request):
    events = selectors.get_upcoming_events().prefetch_related('links')
    return render(request, 'events/upcoming.html', {'events': events})

def past_events(request):
    events = selectors.get_past_events().prefetch_related('links')
    return render(request, 'events/past.html', {'events': events})


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
    # Strip HTML tags and replace &nbsp; with space
    plain_description = strip_tags(event.description or '').replace('&nbsp;', ' ')
    ical_event.add('description', plain_description)
    ical_event.add('uid', f'event-{event.id}@namets.org')
    ical_event.add('dtstamp', timezone.now())

    cal.add_component(ical_event)

    response = HttpResponse(cal.to_ical(), content_type='text/calendar')
    response['Content-Disposition'] = f'attachment; filename="{event.slug}.ics"'
    return response



# ============================================================
# ADMIN/EXCO VIEWS
# ============================================================

@login_required
def event_admin_list(request):
    """EXCO dashboard — full list with search, filters, pagination."""
    if not request.user.has_perm('events.view_event'):
        messages.error(request, "You don't have permission to view events.")
        return redirect('dashboards:dashboard')

    query = request.GET.get('q', '')
    category_filter = request.GET.get('category', '')
    status_filter = request.GET.get('status', '')

    events = Event.objects.all().order_by('-is_featured', 'start_datetime')

    if query:
        events = events.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(location__icontains=query)
        )

    if category_filter:
        events = events.filter(category__slug=category_filter)

    if status_filter:
        now = timezone.now()
        if status_filter == 'upcoming':
            events = events.filter(start_datetime__gt=now)
        elif status_filter == 'ongoing':
            events = events.filter(start_datetime__lte=now, end_datetime__gte=now)
        elif status_filter == 'past':
            events = events.filter(end_datetime__lt=now)

    paginator = Paginator(events, 12)
    page = request.GET.get('page')
    events_page = paginator.get_page(page)

    categories = EventCategory.objects.all()

    return render(request, 'events/admin/event_list.html', {
        'events': events_page,
        'page_obj': events_page,
        'is_paginated': events_page.has_other_pages(),
        'query': query,
        'category_filter': category_filter,
        'status_filter': status_filter,
        'categories': categories,
    })


@login_required
def event_create(request):
    """Create a new event."""
    if not request.user.has_perm('events.add_event'):
        messages.error(request, "You don't have permission to create events.")
        return redirect('events:event_admin_list')

    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        formset = EventLinkFormSet(request.POST, instance=Event())

        if form.is_valid() and formset.is_valid():
            event = form.save()
            formset.instance = event
            formset.save()

            # Trigger email if send_email is checked
            if event.send_email:
                # TODO: Use email engine to notify subscribers
                pass

            messages.success(request, f"✅ Event '{event.title}' created successfully!")
            return redirect('events:event_admin_list')
    else:
        form = EventForm(initial={
            'is_active': True,
        })
        formset = EventLinkFormSet(instance=Event())

    categories = EventCategory.objects.all()

    return render(request, 'events/admin/event_form.html', {
        'form': form,
        'formset': formset,
        'categories': categories,
        'title': 'Create Event',
        'button_text': 'Create Event',
    })


@login_required
def event_edit(request, slug):
    """Edit an existing event."""
    event = get_object_or_404(Event, slug=slug)

    if not request.user.has_perm('events.change_event'):
        messages.error(request, "You don't have permission to edit this event.")
        return redirect('events:event_admin_list')

    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        formset = EventLinkFormSet(request.POST, instance=event)

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f"✅ Event '{event.title}' updated successfully!")
            return redirect('events:event_admin_list')
    else:
        form = EventForm(instance=event)
        formset = EventLinkFormSet(instance=event)

    categories = EventCategory.objects.all()

    return render(request, 'events/admin/event_form.html', {
        'form': form,
        'formset': formset,
        'event': event,
        'categories': categories,
        'title': 'Edit Event',
        'button_text': 'Update Event',
    })


@login_required
def event_delete(request, slug):
    """Delete an event with confirmation."""
    event = get_object_or_404(Event, slug=slug)

    if not request.user.has_perm('events.delete_event'):
        messages.error(request, "You don't have permission to delete this event.")
        return redirect('events:event_admin_list')

    if request.method == 'POST':
        title = event.title
        event.delete()
        messages.success(request, f"🗑️ Event '{title}' deleted successfully!")
        return redirect('events:event_admin_list')

    return render(request, 'events/admin/event_confirm_delete.html', {
        'event': event,
    })



@login_required
def ai_draft_event(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    bullet_points = request.POST.get('bullet_points', '').strip()
    if not bullet_points:
        return JsonResponse({'error': 'Please enter some bullet points first.'}, status=400)

    try:
        # Initialize the new client
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        prompt = f"""
You are an assistant for NAMETS (National Association of Muslim Engineering and Technology Students, ABU Zaria).

The user has given you rough bullet points for an event. Write a warm, professional, and engaging event description in NAMETS's voice.
Keep it concise (2-3 short paragraphs), friendly, and clear. Use the bullet points to form the content.

Here are the bullet points:
{bullet_points}

Return only the description text, nothing else.
"""

        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
            config=GenerateContentConfig(temperature=0.7)
        )

        draft = response.text.strip()
        return JsonResponse({'draft': draft})

    except Exception as e:
        return JsonResponse({'error': f'AI error: {str(e)}'}, status=500)

