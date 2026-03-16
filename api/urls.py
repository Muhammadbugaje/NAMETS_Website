from django.urls import path
from . import views

urlpatterns = [
    path('subscribers/', views.get_subscribers, name='api_subscribers'),
    path('announcements/new/', views.new_announcements, name='api_new_announcements'),
    path('events/upcoming/', views.upcoming_events, name='api_upcoming_events'),
    path('prayer/today/', views.today_prayer, name='api_today_prayer'),
]