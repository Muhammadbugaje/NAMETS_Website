from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

class N8NAuthentication(BaseAuthentication):
    def authenticate(self, request):
        token = request.headers.get('X-N8N-Token')
        if not token or token != settings.N8N_API_TOKEN:
            raise AuthenticationFailed('Invalid or missing token')
        return (None, None)  # No user, just authenticated