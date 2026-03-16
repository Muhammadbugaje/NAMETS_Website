from django.urls import path

from communications.views_api import send_custom_message
from . import views
from . import views_admin

app_name = 'communications'

urlpatterns = [
    path('announcements/', views.announcement_list, name='announcement_list'),
    path('announcements/<slug:slug>/', views.announcement_detail, name='announcement_detail'),
    path('prayer-times/', views.prayer_times, name='prayer_times'),
    path('donations/', views.donation_list, name='donation_list'),
    path('mosque/', views.mosque_info, name='mosque_info'),
    path('subscribe/', views.subscribe, name='subscribe'),
    path('subscribe/success/', views.subscribe_success, name='subscribe_success'),
    path('unsubscribe/<uuid:token>/', views.unsubscribe, name='unsubscribe'),
    path('unsubscribe/', views.unsubscribe_by_email, name='unsubscribe_by_email'),
    # path('admin/communications/send-custom-message/', send_custom_message, name='admin_send_custom_message'),
    # path('send-custom-message/', views_admin.send_custom_message, name='admin_send_custom_message')
]