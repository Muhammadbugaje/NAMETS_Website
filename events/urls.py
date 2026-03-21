from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    path('', views.event_list, name='list'),
    path('upcoming/', views.upcoming_events, name='upcoming'),
    path('past/', views.past_events, name='past'),
    path('<slug:slug>/', views.event_detail, name='detail'),
    path('calendar/<slug:slug>/', views.calendar_ics, name='calendar_ics'),
]