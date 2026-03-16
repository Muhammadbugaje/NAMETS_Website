from django.urls import path
from . import views_api


urlpatterns = [
    path('subscribers/', views_api.get_subscribers, name='api_subscribers'),
    path('announcements/new/', views_api.new_announcements, name='api_new_announcements'),
]