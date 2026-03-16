from .models import Item

def get_lost_items():
    return Item.objects.filter(status='lost', is_active=True).order_by('-reported_at')

def get_found_items():
    return Item.objects.filter(status='found', is_active=True).order_by('-reported_at')

def get_claimed_items():
    return Item.objects.filter(status='claimed', is_active=True).order_by('-claimed_at')

def get_recent_unclaimed(limit=5):
    return Item.objects.filter(status__in=['lost', 'found'], is_active=True).order_by('-reported_at')[:limit]