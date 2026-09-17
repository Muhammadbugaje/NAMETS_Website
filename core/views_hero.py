"""
EXCO-facing admin views for Hero Slide management.
Lives in `core` because that's where the model lives.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from .models import HeroSlide


def _can_manage_hero(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    if user.has_perm('core.add_heroslide') or user.has_perm('core.change_heroslide'):
        return True
    # ICT Head office
    return user.office_assignments.filter(
        is_active=True,
        office__name__icontains='ict',
    ).exists()


@login_required
def hero_slide_list(request):
    if not _can_manage_hero(request.user):
        messages.error(request, "Only the ICT Head can manage hero slides.")
        return redirect('dashboards:dashboard')

    slides = HeroSlide.objects.all().order_by('order', '-created_at')

    return render(request, 'core/admin/hero_slide_list.html', {
        'slides': slides,
        'total': slides.count(),
        'active_count': slides.filter(is_active=True).count(),
    })


@login_required
def hero_slide_form(request, pk=None):
    if not _can_manage_hero(request.user):
        messages.error(request, "Only the ICT Head can manage hero slides.")
        return redirect('dashboards:dashboard')

    slide = get_object_or_404(HeroSlide, pk=pk) if pk else None

    if request.method == 'POST':
        # ---- text ----
        title    = (request.POST.get('title') or '').strip()
        subtitle = (request.POST.get('subtitle') or '').strip()

        # ---- primary button ----
        primary_text = (request.POST.get('primary_button_text') or '').strip()
        primary_url  = (request.POST.get('primary_button_url') or '').strip()

        # ---- secondary button ----
        secondary_text = (request.POST.get('secondary_button_text') or '').strip()
        secondary_url  = (request.POST.get('secondary_button_url') or '').strip()

        # ---- visibility / order ----
        is_active = 'is_active' in request.POST
        order_raw = (request.POST.get('order') or '0').strip()

        # ---- optional scheduling ----
        active_from_raw  = (request.POST.get('active_from') or '').strip()
        active_until_raw = (request.POST.get('active_until') or '').strip()

        try:
            order = int(order_raw)
        except ValueError:
            order = 0

        errors = []

        # ---- button pair validation ----
        if bool(primary_text) ^ bool(primary_url):
            errors.append("Primary button: fill in both the text and the URL, or leave both blank.")
        if bool(secondary_text) ^ bool(secondary_url):
            errors.append("Secondary button: fill in both the text and the URL, or leave both blank.")

        # ---- images ----
        desktop_file = request.FILES.get('desktop_image')
        mobile_file  = request.FILES.get('mobile_image')

        if slide is None:
            if not desktop_file:
                errors.append("Desktop image is required.")
            if not mobile_file:
                errors.append("Mobile image is required.")

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            if slide is None:
                slide = HeroSlide()

            slide.title    = title
            slide.subtitle = subtitle

            slide.primary_button_text = primary_text
            slide.primary_button_url  = primary_url
            slide.secondary_button_text = secondary_text
            slide.secondary_button_url  = secondary_url

            slide.is_active = is_active
            slide.order     = order

            # ---- scheduling ----
            slide.active_from  = parse_datetime(active_from_raw) if active_from_raw else None
            slide.active_until = parse_datetime(active_until_raw) if active_until_raw else None

            # ---- images (only replace if a new file was uploaded) ----
            if desktop_file:
                if slide.pk and slide.desktop_image:
                    try:
                        slide.desktop_image.delete(save=False)
                    except Exception:
                        pass
                slide.desktop_image = desktop_file

            if mobile_file:
                if slide.pk and slide.mobile_image:
                    try:
                        slide.mobile_image.delete(save=False)
                    except Exception:
                        pass
                slide.mobile_image = mobile_file

            slide.save()

            messages.success(request, f"✅ Hero slide “{slide.title or f'#{slide.pk}'}” saved.")
            return redirect('core:hero_slide_list')

    return render(request, 'core/admin/hero_slide_form.html', {
        'slide': slide,
        'is_edit': slide is not None,
    })


@require_POST
@login_required
def hero_slide_delete(request, pk):
    if not _can_manage_hero(request.user):
        messages.error(request, "Only the ICT Head can manage hero slides.")
        return redirect('dashboards:dashboard')

    slide = get_object_or_404(HeroSlide, pk=pk)
    label = slide.title or f"slide #{slide.pk}"

    # Clean up files
    for field in (slide.desktop_image, slide.mobile_image):
        try:
            if field:
                field.delete(save=False)
        except Exception:
            pass

    slide.delete()
    messages.success(request, f"🗑️ Hero slide “{label}” deleted.")
    return redirect('core:hero_slide_list')


@require_POST
@login_required
def hero_slide_toggle(request, pk):
    if not _can_manage_hero(request.user):
        messages.error(request, "Only the ICT Head can manage hero slides.")
        return redirect('dashboards:dashboard')

    slide = get_object_or_404(HeroSlide, pk=pk)
    slide.is_active = not slide.is_active
    slide.save(update_fields=['is_active', 'updated_at'])
    state = "activated" if slide.is_active else "hidden"
    messages.success(request, f"Hero slide {state}.")
    return redirect('core:hero_slide_list')