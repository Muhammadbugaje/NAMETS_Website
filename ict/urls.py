from django.urls import path
from . import views

app_name = 'ict'

# ict/urls.py

urlpatterns = [
    path('users/', views.user_list, name='user_list'),
    path('users/add/', views.add_user, name='add_user'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('users/<int:user_id>/edit/', views.edit_user, name='edit_user'),
    path('users/<int:user_id>/toggle-status/', views.toggle_user_status, name='toggle_user_status'),
    path('users/<int:user_id>/assign-office/', views.assign_office, name='assign_office'),
    path('users/<int:user_id>/resend-credentials/', views.resend_credentials, name='resend_credentials'),
    path('users/<int:user_id>/delete/', views.delete_user, name='delete_user'),
    path('remove-office/<int:assignment_id>/', views.remove_office, name='remove_office'),
    path('email-logs/', views.email_logs, name='email_logs'),
    path('email-logs/resend/<int:log_id>/', views.resend_failed_email, name='resend_failed_email'),

    path('users/import-exco/', views.import_exco, name='import_exco'),

]
