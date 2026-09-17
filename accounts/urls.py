from django.urls import path
from django.contrib.auth import views as auth_views
from . import views as custom_views

app_name = 'accounts'

urlpatterns = [
    # Hidden login
    path('namets-exco/', custom_views.portal_entry, name='portal_entry'),
    path('change-password/', custom_views.force_password_change, name='force_password_change'),
    path('profile/', custom_views.profile_update, name='profile_update'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # Password reset — using custom view
    path('password-reset/',
         custom_views.CustomPasswordResetView.as_view(),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='accounts/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='accounts/password_reset_confirm.html',
             success_url='/accounts/password-reset/complete/'
         ),
         name='password_reset_confirm'),

    path('password-reset/complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='accounts/password_reset_complete.html'
         ),
         name='password_reset_complete'),
]
