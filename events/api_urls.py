from django.urls import path
from . import views_api

urlpatterns = [
    path('upcoming/', views_api.upcoming_events, name='api_upcoming_events'),
]