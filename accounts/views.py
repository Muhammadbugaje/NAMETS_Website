from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth.views import PasswordResetView
from django.urls import reverse_lazy
from django.contrib import messages
from core.email_utils import send_templated_email
from django.utils.html import strip_tags

from .forms import CustomPasswordResetForm


def portal_entry(request):
    """Hidden login page — URL is never linked publicly."""
    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('email'),
            password=request.POST.get('password'),
        )
        if user is not None:
            auth_login(request, user)
            if user.must_change_password:
                return redirect('accounts:force_password_change')
            return redirect('dashboards:dashboard')
        messages.error(request, "Invalid credentials.")
    return render(request, 'accounts/portal_entry.html')



@login_required
def force_password_change(request):
    """Allow logged-in users to change their password."""
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        if new_password == confirm_password and len(new_password) >= 8:
            request.user.set_password(new_password)
            request.user.must_change_password = False
            request.user.save(update_fields=['password', 'must_change_password'])
            messages.success(request, "Password updated successfully.")
            return redirect('accounts:profile_update')
        messages.error(request, "Passwords must match and be at least 8 characters.")
    return render(request, 'accounts/force_password_change.html')

@login_required
def profile_update(request):
    """Update user profile with photo removal and completion bar."""
    user = request.user

    if request.method == 'POST':
        # Update basic fields
        for field in ['first_name', 'last_name', 'middle_name', 'phone_number', 'address']:
            setattr(user, field, request.POST.get(field, getattr(user, field)))

        # Update social links
        social_links = {
            'twitter': request.POST.get('twitter', ''),
            'instagram': request.POST.get('instagram', ''),
            'linkedin': request.POST.get('linkedin', ''),
            'whatsapp': request.POST.get('whatsapp', ''),
            'facebook': request.POST.get('facebook', ''),
        }
        user.social_links = {k: v for k, v in social_links.items() if v}

        # Update department
        dept_name = request.POST.get('department', '').strip()
        if dept_name:
            from .models import Department
            dept, _ = Department.objects.get_or_create(
                name=dept_name,
                defaults={'code': dept_name[:10].upper()}
            )
            user.department = dept
        else:
            user.department = None

        # Handle profile picture — delete old before saving new
        if 'remove_photo' in request.POST:
            if user.profile_picture:
                user.profile_picture.delete(save=False)
                user.profile_picture = None
        elif request.FILES.get('profile_picture'):
            if user.profile_picture:
                user.profile_picture.delete(save=False)
            user.profile_picture = request.FILES['profile_picture']

        user.save()
        user.calculate_profile_completion()

        messages.success(request, "Profile updated successfully.")
        return redirect('accounts:profile_update')

    return render(request, 'accounts/profile.html', {
        'user': user,
        'pct': user.profile_completion_percentage,
    })
    
    

class CustomPasswordResetView(PasswordResetView):
    form_class = CustomPasswordResetForm
    template_name = 'accounts/password_reset_form.html'
    email_template_name = 'accounts/password_reset_email.html'
    subject_template_name = 'accounts/password_reset_subject.txt'
    success_url = reverse_lazy('accounts:password_reset_done')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['logo_url'] = getattr(settings, 'LOGO_URL', 'https://namets.org/static/images/Namets.jpg')
        return context