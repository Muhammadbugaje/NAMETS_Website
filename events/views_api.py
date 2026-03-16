from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from .models import Event
from .serializers import EventSerializer
from django.utils import timezone
from datetime import timedelta
from utils.auth import N8NAuthentication

@api_view(['GET'])
@authentication_classes([N8NAuthentication])
@permission_classes([])
def upcoming_events(request):
    # Events in the next N days (default 7)
    days = int(request.GET.get('days', 7))
    now = timezone.now()
    end = now + timedelta(days=days)
    qs = Event.objects.filter(start_datetime__gte=now, start_datetime__lte=end, is_active=True)
    serializer = EventSerializer(qs, many=True)
    return Response(serializer.data)