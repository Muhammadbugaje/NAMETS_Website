from .selectors import get_active_developers
from .models import ContactPhone, SocialMediaLink

def developers(request):
    return {'developers': get_active_developers()}


def contact_phones(request):
    return {'contact_phones': ContactPhone.objects.filter(is_active=True)}

def social_links(request):
    return {
        'social_links': SocialMediaLink.objects.filter(is_active=True).order_by('order')
    }