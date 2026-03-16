from django.shortcuts import render
from communications.selectors import get_next_prayer, get_pinned_announcements, get_active_donation_campaigns
from events.selectors import get_featured_events, get_upcoming_events
from academics.selectors import get_upcoming_sessions  
from lostfound.selectors import get_recent_unclaimed
from community.selectors import get_active_developers, get_featured_patron
from gallery.selectors import get_recent_gallery_images

def homepage(request):
    context = {
        'next_prayer': get_next_prayer(),
        'pinned_announcements': get_pinned_announcements()[:3],
        'featured_event': get_featured_events().first(),
        'upcoming_events': get_upcoming_events()[:3],
        'upcoming_sessions': get_upcoming_sessions()[:5],  # adjust limit
        'recent_items': get_recent_unclaimed()[:2],  # show 2 recent lost/found items
        'featured_patron': get_featured_patron(),
        'active_developers': get_active_developers()[:3],
        'active_campaigns': get_active_donation_campaigns()[:2],
        'recent_gallery_images': get_recent_gallery_images(6),
    }
    return render(request, 'core/homepage.html', context)