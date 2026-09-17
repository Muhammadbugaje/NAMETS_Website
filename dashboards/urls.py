from django.urls import path
from . import views

app_name = 'dashboards'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('switch/<int:assignment_id>/', views.switch_office, name='switch_office'),
    path('manage-permissions/', views.manage_permissions, name='manage_permissions'),
    path('reassign/', views.reassign_office, name='reassign_office'),
    path('offices/', views.office_directory, name='office_directory'),
    path('activity/', views.activity_log, name='activity_log'),

    path('alumni/', views.alumni_dashboard, name='alumni_dashboard'),
    path('directory/', views.alumni_directory, name='alumni_directory'),


    # Inbox
    path('inbox/', views.inbox, name='inbox'),
    path('inbox/mark-read/<int:pk>/', views.inbox_mark_read, name='inbox_mark_read'),
    path('inbox/mark-all-read/', views.inbox_mark_all_read, name='inbox_mark_all_read'),
    path('inbox/unread-count/', views.unread_count_api, name='unread_count_api'),


    # ============================================================
    # MESSAGING (user-to-user — separate from notifications)
    # ============================================================
    path('messages/', views.messages_inbox, name='messages'),
    path('messages/sent/', views.messages_sent, name='messages_sent'),
    path('messages/compose/', views.message_compose, name='message_compose'),
    path('messages/<int:pk>/', views.message_detail, name='message_detail'),
    path('messages/<int:pk>/delete/', views.message_delete, name='message_delete'),
    path('messages/<int:pk>/pin/', views.message_toggle_pin, name='message_toggle_pin'),
    path('messages/unread-count/', views.messages_unread_api, name='messages_unread_api'),
]

