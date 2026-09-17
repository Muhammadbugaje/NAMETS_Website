from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    # ===== PUBLIC VIEWS =====
    path('', views.event_list, name='list'),
    path('upcoming/', views.upcoming_events, name='upcoming'),
    path('past/', views.past_events, name='past'),

    # ===== ADMIN/EXCO VIEWS — MUST COME BEFORE THE GENERIC SLUG PATTERN =====
    path('admin/', views.event_admin_list, name='event_admin_list'),
    path('admin/create/', views.event_create, name='event_create'),
    path('admin/<slug:slug>/edit/', views.event_edit, name='event_edit'),
    path('admin/<slug:slug>/delete/', views.event_delete, name='event_delete'),
    path('admin/ai-draft/', views.ai_draft_event, name='ai_draft_event'),

    # ===== GENERIC SLUG PATTERNS (MUST BE LAST) =====
    path('<slug:slug>/', views.event_detail, name='detail'),
    path('calendar/<slug:slug>/', views.calendar_ics, name='calendar_ics'),
]