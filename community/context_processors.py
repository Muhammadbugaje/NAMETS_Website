from .selectors import get_active_developers

def developers(request):
    return {'developers': get_active_developers()}