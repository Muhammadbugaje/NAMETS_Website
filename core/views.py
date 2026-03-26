from django.shortcuts import render
from django.core.cache import cache
from communications.selectors import get_next_prayer, get_pinned_announcements, get_active_donation_campaigns
from events.selectors import get_featured_events, get_upcoming_events
from academics.selectors import get_upcoming_sessions
from lostfound.selectors import get_recent_unclaimed
from community.selectors import get_active_developers, get_featured_patron
from gallery.selectors import get_recent_gallery_images

def get_cached(key, func, timeout=60):
    data = cache.get(key)
    if data is None:
        data = func()
        cache.set(key, data, timeout)
    return data

def homepage(request):
    context = {
        'next_prayer': get_cached('hp_prayer', get_next_prayer, 60 * 60 * 6),
        'pinned_announcements': get_cached('hp_announcements', lambda: get_pinned_announcements()[:3], 60 * 2),
        'featured_event': get_cached('hp_featured_event', lambda: get_featured_events().first(), 60 * 3),
        'upcoming_events': get_cached('hp_upcoming_events', lambda: get_upcoming_events()[:3], 60 * 3),
        'upcoming_sessions': get_cached('hp_sessions', lambda: get_upcoming_sessions()[:5], 60 * 5),
        'recent_items': get_cached('hp_lost_found', lambda: get_recent_unclaimed()[:2], 60 * 5),
        'featured_patron': get_cached('hp_patron', get_featured_patron, 60 * 10),
        'active_developers': get_cached('hp_developers', lambda: get_active_developers()[:3], 60 * 10),
        'active_campaigns': get_cached('hp_campaigns', lambda: get_active_donation_campaigns()[:2], 60 * 5),
        'recent_gallery_images': get_cached('hp_gallery', lambda: get_recent_gallery_images(6), 60 * 10),
    }
    return render(request, 'core/homepage.html', context)