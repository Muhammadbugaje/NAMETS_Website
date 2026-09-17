
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

import uuid

from google import genai
from google.genai.types import GenerateContentConfig

from .models import (
    Announcement, PrayerSchedule, DonationCampaign, MosqueInfo, MosqueRule,
    MagazineIssue, Article, Subscriber, Link
)
from . import selectors
from .forms import (
    SubscriptionForm, AnnouncementForm, LinkFormSet,
    PrayerScheduleForm, DonationCampaignForm, MosqueInfoForm, MosqueRuleForm,
    MagazineIssueForm, ArticleForm, SubscriberForm,
)
from core.email_utils import send_templated_email
from core.importers.excel_io import build_export_xlsx
from core.importers.spec import ColumnSpec, ImportSpec
from accounts.models import Office

User = get_user_model()


# ============================================================
# PUBLIC VIEWS
# ============================================================

def announcement_list(request):
    """Public announcement list with search, category filter, and pagination."""
    query = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '').strip()

    announcements = selectors.get_active_announcements()

    if query:
        announcements = announcements.filter(
            Q(title__icontains=query) | Q(content__icontains=query)
        )

    if category_filter:
        announcements = announcements.filter(category=category_filter)

    announcements = announcements.order_by('-is_pinned', '-publish_at')

    paginator = Paginator(announcements, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = Announcement.CATEGORY_CHOICES

    return render(request, 'communications/announcement_list.html', {
        'announcements': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'query': query,
        'category_filter': category_filter,
        'categories': categories,
    })


def announcement_detail(request, slug):
    announcement = get_object_or_404(Announcement, slug=slug, is_active=True)
    return render(request, 'communications/announcement_detail.html', {'announcement': announcement})


def prayer_times(request):
    schedule = selectors.get_today_prayer_schedule()
    return render(request, 'communications/prayer_times.html', {'schedule': schedule})


def donation_list(request):
    campaigns = selectors.get_active_donation_campaigns()
    return render(request, 'communications/donation_list.html', {'campaigns': campaigns})


def mosque_info(request):
    info = selectors.get_mosque_info()
    rules = selectors.get_active_mosque_rules()
    return render(request, 'communications/mosque_info.html', {'info': info, 'rules': rules})


def subscribe(request):
    if request.method == 'POST':
        form = SubscriptionForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            new_prefs = {
                'notify_announcements': form.cleaned_data.get('notify_announcements', False),
                'notify_events': form.cleaned_data.get('notify_events', False),
                'notify_prayer_changes': form.cleaned_data.get('notify_prayer_changes', False),
            }

            try:
                subscriber = Subscriber.objects.get(email=email)
                current_prefs = {
                    'notify_announcements': subscriber.notify_announcements,
                    'notify_events': subscriber.notify_events,
                    'notify_prayer_changes': subscriber.notify_prayer_changes,
                }

                if current_prefs != new_prefs:
                    request.session['pending_subscription'] = {
                        'email': email,
                        'new_prefs': new_prefs,
                        'current_prefs': current_prefs,
                    }
                    request.session.modified = True
                    return redirect('communications:confirm_subscription')
                else:
                    messages.info(request, "You're already subscribed with these preferences.")
                    return redirect('core:homepage')

            except Subscriber.DoesNotExist:
                Subscriber.objects.create(
                    email=email,
                    token=uuid.uuid4(),
                    is_verified=False,
                    is_active=True,
                    **new_prefs
                )
                messages.success(request, "You've subscribed successfully!", extra_tags='subscribe_success')
                return redirect('core:homepage')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            return redirect('core:homepage')
    else:
        return redirect('core:homepage')


def confirm_subscription(request):
    pending = request.session.get('pending_subscription')

    if not pending:
        messages.error(request, 'No pending request found. Please try again.')
        return redirect('core:homepage')

    if request.method == 'POST':
        email = pending['email']
        new_prefs = pending['new_prefs']
        current_prefs = pending['current_prefs']

        try:
            subscriber = Subscriber.objects.get(email__iexact=email)
        except Subscriber.DoesNotExist:
            messages.error(request, 'Subscriber not found.')
            return redirect('core:homepage')

        subscriber.notify_announcements = new_prefs['notify_announcements']
        subscriber.notify_events = new_prefs['notify_events']
        subscriber.notify_prayer_changes = new_prefs['notify_prayer_changes']
        subscriber.save(update_fields=[
            'notify_announcements', 'notify_events', 'notify_prayer_changes'
        ])

        send_templated_email(
            subject="As Salamu Alaikum, Your NAMETS preferences have been updated",
            recipients=[email],
            template_name='emails/preference_updated.html',
            context={
                'new_preferences': new_prefs,
                'current_preferences': current_prefs,
            },
        )

        del request.session['pending_subscription']
        messages.success(request, 'Your preferences have been updated!')
        return redirect('core:homepage')

    return render(request, 'communications/confirm_subscription.html', {
        'email': pending['email'],
        'current_prefs': pending['current_prefs'],
        'new_prefs': pending['new_prefs'],
    })


def subscribe_success(request):
    return render(request, 'communications/subscribe_success.html')


def unsubscribe(request, token):
    subscriber = get_object_or_404(Subscriber, token=token)
    if request.method == 'POST':
        email = subscriber.email
        subscriber.delete()
        messages.success(request, f'{email} has been unsubscribed and removed from our records.')
        return redirect('core:homepage')
    return render(request, 'communications/unsubscribe_confirm.html', {'subscriber': subscriber})


def unsubscribe_by_email(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        if not email:
            messages.error(request, 'Please enter an email address.')
            return redirect('communications:unsubscribe_by_email')

        subscriber = Subscriber.objects.filter(email__iexact=email, is_active=True).first()
        if subscriber:
            unsubscribe_url = request.build_absolute_uri(
                reverse('communications:unsubscribe', args=[subscriber.token])
            )
            send_templated_email(
                subject="Confirm your NAMETS unsubscribe request",
                recipients=[subscriber.email],
                template_name='emails/unsubscribe_confirm.html',
                context={
                    'email': subscriber.email,
                    'unsubscribe_url': unsubscribe_url,
                },
            )
        messages.success(request, f"If {email} is subscribed, we've sent a confirmation link to it.")
        return redirect('core:homepage')
    return render(request, 'communications/unsubscribe_by_email.html')


def article_list(request):
    articles = Article.objects.filter(is_active=True)
    return render(request, 'communications/article_list.html', {'articles': articles})


def article_detail(request, slug):
    article = get_object_or_404(Article, slug=slug, is_active=True)
    return render(request, 'communications/article_detail.html', {'article': article})


def magazine_list(request):
    issues = MagazineIssue.objects.filter(is_active=True)
    return render(request, 'communications/magazine_list.html', {'issues': issues})


def magazine_detail(request, slug):
    issue = get_object_or_404(MagazineIssue, slug=slug, is_active=True)
    articles = issue.articles.filter(is_active=True)
    return render(request, 'communications/magazine_detail.html', {'issue': issue, 'articles': articles})


# ============================================================
# ANNOUNCEMENT ADMIN
# ============================================================

@login_required
def announcement_admin_list(request):
    if not request.user.has_perm('communications.view_announcement'):
        messages.error(request, "You don't have permission to view announcements.")
        return redirect('dashboards:dashboard')

    query = request.GET.get('q', '')
    category_filter = request.GET.get('category', '')
    status_filter = request.GET.get('status', '')

    announcements = Announcement.objects.all().order_by('-is_pinned', '-publish_at')

    if query:
        announcements = announcements.filter(
            Q(title__icontains=query) | Q(content__icontains=query)
        )

    if category_filter:
        announcements = announcements.filter(category=category_filter)

    if status_filter == 'published':
        announcements = announcements.filter(
            publish_at__lte=timezone.now(),
            is_active=True
        ).exclude(expire_at__lt=timezone.now())
    elif status_filter == 'draft':
        announcements = announcements.filter(publish_at__gt=timezone.now())
    elif status_filter == 'expired':
        announcements = announcements.filter(expire_at__lt=timezone.now())

    paginator = Paginator(announcements, 20)
    page = request.GET.get('page')
    announcements_page = paginator.get_page(page)

    categories = Announcement.CATEGORY_CHOICES

    return render(request, 'communications/admin/announcement_list.html', {
        'announcements': announcements_page,
        'query': query,
        'category_filter': category_filter,
        'status_filter': status_filter,
        'categories': categories,
    })


@login_required
def announcement_create(request):
    if not request.user.has_perm('communications.add_announcement'):
        messages.error(request, "You don't have permission to create announcements.")
        return redirect('communications:announcement_admin_list')

    if request.method == 'POST':
        form = AnnouncementForm(request.POST, request.FILES)
        formset = LinkFormSet(request.POST, instance=Announcement())

        if form.is_valid() and formset.is_valid():
            announcement = form.save(commit=False)
            announcement.created_by = request.user
            announcement.save()
            formset.instance = announcement
            formset.save()

            messages.success(request, f"✅ Announcement '{announcement.title}' created successfully!")
            return redirect('communications:announcement_admin_list')
    else:
        form = AnnouncementForm(initial={
            'publish_at': timezone.now(),
            'is_active': True,
        })
        formset = LinkFormSet(instance=Announcement())

    return render(request, 'communications/admin/announcement_form.html', {
        'form': form,
        'formset': formset,
        'title': 'Create Announcement',
        'button_text': 'Create Announcement',
    })


@login_required
def announcement_edit(request, slug):
    announcement = get_object_or_404(Announcement, slug=slug)

    if not request.user.has_perm('communications.change_announcement'):
        messages.error(request, "You don't have permission to edit this announcement.")
        return redirect('communications:announcement_admin_list')

    if request.method == 'POST':
        form = AnnouncementForm(request.POST, request.FILES, instance=announcement)
        formset = LinkFormSet(request.POST, instance=announcement)

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f"✅ Announcement '{announcement.title}' updated successfully!")
            return redirect('communications:announcement_admin_list')
    else:
        form = AnnouncementForm(instance=announcement)
        formset = LinkFormSet(instance=announcement)

    return render(request, 'communications/admin/announcement_form.html', {
        'form': form,
        'formset': formset,
        'announcement': announcement,
        'title': 'Edit Announcement',
        'button_text': 'Update Announcement',
    })


@login_required
def announcement_delete(request, slug):
    announcement = get_object_or_404(Announcement, slug=slug)

    if not request.user.has_perm('communications.delete_announcement'):
        messages.error(request, "You don't have permission to delete this announcement.")
        return redirect('communications:announcement_admin_list')

    if request.method == 'POST':
        title = announcement.title
        announcement.delete()
        messages.success(request, f"🗑️ Announcement '{title}' deleted successfully!")
        return redirect('communications:announcement_admin_list')

    return render(request, 'communications/admin/announcement_confirm_delete.html', {
        'announcement': announcement,
    })


@login_required
def ai_draft_announcement(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    bullet_points = request.POST.get('bullet_points', '').strip()
    if not bullet_points:
        return JsonResponse({'error': 'Please enter some bullet points first.'}, status=400)

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        prompt = f"""
You are an assistant for NAMETS (National Association of Muslim Engineering and Technology Students, ABU Zaria).

The user has given you rough bullet points for an announcement. Write a warm, professional, and engaging announcement in NAMETS's voice.
Keep it concise (2-3 short paragraphs), friendly, and clear. Use the bullet points to form the content.

Here are the bullet points:
{bullet_points}

Return only the announcement text, nothing else.
"""

        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
            config=GenerateContentConfig(temperature=0.7)
        )

        draft = response.text.strip()
        return JsonResponse({'draft': draft})

    except Exception as e:
        return JsonResponse({'error': f'AI error: {str(e)}'}, status=500)


# ============================================================
# PRAYER SCHEDULE ADMIN
# ============================================================

@login_required
def admin_prayer_list(request):
    if not request.user.has_perm('communications.view_prayerschedule'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    query = request.GET.get('q', '')
    schedules = PrayerSchedule.objects.all().order_by('-date')

    if query:
        schedules = schedules.filter(date__icontains=query)

    paginator = Paginator(schedules, 30)
    page = request.GET.get('page')
    schedules_page = paginator.get_page(page)

    return render(request, 'communications/admin/prayer_list.html', {
        'schedules': schedules_page,
        'page_obj': schedules_page,
        'is_paginated': schedules_page.has_other_pages(),
        'query': query,
    })


@login_required
def admin_prayer_create(request):
    if not request.user.has_perm('communications.add_prayerschedule'):
        messages.error(request, "Permission denied.")
        return redirect('communications:admin_prayer_list')

    if request.method == 'POST':
        form = PrayerScheduleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Prayer schedule created.")
            return redirect('communications:admin_prayer_list')
    else:
        form = PrayerScheduleForm()

    return render(request, 'communications/admin/prayer_form.html', {
        'form': form,
        'title': 'Add Prayer Schedule',
        'button_text': 'Save Schedule',
    })


@login_required
def admin_prayer_edit(request, pk):
    schedule = get_object_or_404(PrayerSchedule, pk=pk)
    if not request.user.has_perm('communications.change_prayerschedule'):
        messages.error(request, "Permission denied.")
        return redirect('communications:admin_prayer_list')

    if request.method == 'POST':
        form = PrayerScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Prayer schedule updated.")
            return redirect('communications:admin_prayer_list')
    else:
        form = PrayerScheduleForm(instance=schedule)

    return render(request, 'communications/admin/prayer_form.html', {
        'form': form,
        'schedule': schedule,
        'title': 'Edit Prayer Schedule',
        'button_text': 'Update Schedule',
    })


@login_required
def admin_prayer_delete(request, pk):
    schedule = get_object_or_404(PrayerSchedule, pk=pk)
    if not request.user.has_perm('communications.delete_prayerschedule'):
        messages.error(request, "Permission denied.")
        return redirect('communications:admin_prayer_list')

    if request.method == 'POST':
        date_str = schedule.date.strftime('%Y-%m-%d')
        schedule.delete()
        messages.success(request, f"🗑️ Prayer schedule for {date_str} deleted.")
        return redirect('communications:admin_prayer_list')

    return render(request, 'communications/admin/prayer_confirm_delete.html', {'schedule': schedule})


# ============================================================
# DONATION CAMPAIGNS ADMIN
# ============================================================

@login_required
def admin_donation_list(request):
    if not request.user.has_perm('communications.view_donationcampaign'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    query = request.GET.get('q', '')
    campaigns = DonationCampaign.objects.all().order_by('-created_at')

    if query:
        campaigns = campaigns.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )

    paginator = Paginator(campaigns, 20)
    page = request.GET.get('page')
    campaigns_page = paginator.get_page(page)

    return render(request, 'communications/admin/donation_list.html', {
        'campaigns': campaigns_page,
        'page_obj': campaigns_page,
        'is_paginated': campaigns_page.has_other_pages(),
        'query': query,
    })


@login_required
def admin_donation_create(request):
    if not request.user.has_perm('communications.add_donationcampaign'):
        messages.error(request, "Permission denied.")
        return redirect('communications:admin_donation_list')

    if request.method == 'POST':
        form = DonationCampaignForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Donation campaign created.")
            return redirect('communications:admin_donation_list')
    else:
        form = DonationCampaignForm()

    return render(request, 'communications/admin/donation_form.html', {
        'form': form,
        'title': 'Create Donation Campaign',
        'button_text': 'Create Campaign',
    })


@login_required
def admin_donation_edit(request, pk):
    campaign = get_object_or_404(DonationCampaign, pk=pk)
    if not request.user.has_perm('communications.change_donationcampaign'):
        messages.error(request, "Permission denied.")
        return redirect('communications:admin_donation_list')

    if request.method == 'POST':
        form = DonationCampaignForm(request.POST, instance=campaign)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Donation campaign updated.")
            return redirect('communications:admin_donation_list')
    else:
        form = DonationCampaignForm(instance=campaign)

    return render(request, 'communications/admin/donation_form.html', {
        'form': form,
        'campaign': campaign,
        'title': 'Edit Donation Campaign',
        'button_text': 'Update Campaign',
    })


@login_required
def admin_donation_delete(request, pk):
    campaign = get_object_or_404(DonationCampaign, pk=pk)
    if not request.user.has_perm('communications.delete_donationcampaign'):
        messages.error(request, "Permission denied.")
        return redirect('communications:admin_donation_list')

    if request.method == 'POST':
        title = campaign.title
        campaign.delete()
        messages.success(request, f"🗑️ Campaign '{title}' deleted.")
        return redirect('communications:admin_donation_list')

    return render(request, 'communications/admin/donation_confirm_delete.html', {'campaign': campaign})


# ============================================================
# MOSQUE INFO (SINGLETON) & RULES
# ============================================================

@login_required
def admin_mosque_edit(request):
    if not request.user.has_perm('communications.change_mosqueinfo'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    info = MosqueInfo.objects.first()
    if not info:
        info = MosqueInfo.objects.create(
            location="Engineering Mosque, ABU Zaria",
            description="The main mosque serving the Faculty of Engineering community."
        )

    if request.method == 'POST':
        form = MosqueInfoForm(request.POST, instance=info)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Mosque info updated.")
            return redirect('communications:admin_mosque_edit')
    else:
        form = MosqueInfoForm(instance=info)

    rules = MosqueRule.objects.filter(is_active=True).order_by('order')

    return render(request, 'communications/admin/mosque_edit.html', {
        'form': form,
        'rules': rules,
        'info': info,
    })


@login_required
def admin_mosque_rule_list(request):
    if not request.user.has_perm('communications.view_mosquerule'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    rules = MosqueRule.objects.all().order_by('order')
    return render(request, 'communications/admin/mosque_rule_list.html', {'rules': rules})


@login_required
def admin_mosque_rule_create(request):
    if not request.user.has_perm('communications.add_mosquerule'):
        messages.error(request, "Permission denied.")
        return redirect('communications:admin_mosque_rule_list')

    if request.method == 'POST':
        form = MosqueRuleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Mosque rule added.")
            return redirect('communications:admin_mosque_rule_list')
    else:
        form = MosqueRuleForm()

    return render(request, 'communications/admin/mosque_rule_form.html', {
        'form': form,
        'title': 'Add Mosque Rule',
        'button_text': 'Add Rule',
    })


@login_required
def admin_mosque_rule_edit(request, pk):
    rule = get_object_or_404(MosqueRule, pk=pk)
    if not request.user.has_perm('communications.change_mosquerule'):
        messages.error(request, "Permission denied.")
        return redirect('communications:admin_mosque_rule_list')

    if request.method == 'POST':
        form = MosqueRuleForm(request.POST, instance=rule)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Mosque rule updated.")
            return redirect('communications:admin_mosque_rule_list')
    else:
        form = MosqueRuleForm(instance=rule)

    return render(request, 'communications/admin/mosque_rule_form.html', {
        'form': form,
        'rule': rule,
        'title': 'Edit Mosque Rule',
        'button_text': 'Update Rule',
    })


@login_required
def admin_mosque_rule_delete(request, pk):
    rule = get_object_or_404(MosqueRule, pk=pk)
    if not request.user.has_perm('communications.delete_mosquerule'):
        messages.error(request, "Permission denied.")
        return redirect('communications:admin_mosque_rule_list')

    if request.method == 'POST':
        title = rule.title
        rule.delete()
        messages.success(request, f"🗑️ Rule '{title}' deleted.")
        return redirect('communications:admin_mosque_rule_list')

    return render(request, 'communications/admin/mosque_rule_confirm_delete.html', {'rule': rule})


# ============================================================
# MAGAZINE ISSUES ADMIN
# ============================================================

@login_required
def admin_magazine_list(request):
    if not request.user.has_perm('communications.view_magazineissue'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    query = request.GET.get('q', '')
    issues = MagazineIssue.objects.all().order_by('-published_date')

    if query:
        issues = issues.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )

    paginator = Paginator(issues, 12)
    page = request.GET.get('page')
    issues_page = paginator.get_page(page)

    return render(request, 'communications/admin/magazine_list.html', {
        'issues': issues_page,
        'page_obj': issues_page,
        'is_paginated': issues_page.has_other_pages(),
        'query': query,
    })


@login_required
def admin_magazine_create(request):
    if not request.user.has_perm('communications.add_magazineissue'):
        messages.error(request, "Permission denied.")
        return redirect('communications:admin_magazine_list')

    if request.method == 'POST':
        form = MagazineIssueForm(request.POST, request.FILES)
        if form.is_valid():
            issue = form.save()
            messages.success(request, f"✅ Magazine '{issue.title}' created.")
            return redirect('communications:admin_magazine_list')
    else:
        form = MagazineIssueForm()

    return render(request, 'communications/admin/magazine_form.html', {
        'form': form,
        'title': 'Create Magazine Issue',
        'button_text': 'Create Issue',
    })


@login_required
def admin_magazine_edit(request, slug):
    issue = get_object_or_404(MagazineIssue, slug=slug)
    if not request.user.has_perm('communications.change_magazineissue'):
        messages.error(request, "Permission denied.")
        return redirect('communications:admin_magazine_list')

    if request.method == 'POST':
        form = MagazineIssueForm(request.POST, request.FILES, instance=issue)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Magazine '{issue.title}' updated.")
            return redirect('communications:admin_magazine_list')
    else:
        form = MagazineIssueForm(instance=issue)

    return render(request, 'communications/admin/magazine_form.html', {
        'form': form,
        'issue': issue,
        'title': 'Edit Magazine Issue',
        'button_text': 'Update Issue',
    })


@login_required
def admin_magazine_delete(request, slug):
    issue = get_object_or_404(MagazineIssue, slug=slug)
    if not request.user.has_perm('communications.delete_magazineissue'):
        messages.error(request, "Permission denied.")
        return redirect('communications:admin_magazine_list')

    if request.method == 'POST':
        title = issue.title
        issue.delete()
        messages.success(request, f"🗑️ Magazine '{title}' deleted.")
        return redirect('communications:admin_magazine_list')

    return render(request, 'communications/admin/magazine_confirm_delete.html', {'issue': issue})


# ============================================================
# ARTICLES ADMIN
# ============================================================

@login_required
def admin_article_list(request):
    if not request.user.has_perm('communications.view_article'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    query = request.GET.get('q', '')
    articles = Article.objects.all().order_by('-published_at')

    if query:
        articles = articles.filter(
            Q(title__icontains=query) |
            Q(content__icontains=query) |
            Q(author__icontains=query)
        )

    paginator = Paginator(articles, 20)
    page = request.GET.get('page')
    articles_page = paginator.get_page(page)

    return render(request, 'communications/admin/article_list.html', {
        'articles': articles_page,
        'page_obj': articles_page,
        'is_paginated': articles_page.has_other_pages(),
        'query': query,
    })


@login_required
def admin_article_create(request):
    if not request.user.has_perm('communications.add_article'):
        messages.error(request, "Permission denied.")
        return redirect('communications:admin_article_list')

    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES)
        if form.is_valid():
            article = form.save()
            messages.success(request, f"✅ Article '{article.title}' created.")
            return redirect('communications:admin_article_list')
    else:
        form = ArticleForm()

    return render(request, 'communications/admin/article_form.html', {
        'form': form,
        'title': 'Create Article',
        'button_text': 'Create Article',
    })


@login_required
def admin_article_edit(request, slug):
    article = get_object_or_404(Article, slug=slug)
    if not request.user.has_perm('communications.change_article'):
        messages.error(request, "Permission denied.")
        return redirect('communications:admin_article_list')

    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES, instance=article)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Article '{article.title}' updated.")
            return redirect('communications:admin_article_list')
    else:
        form = ArticleForm(instance=article)

    return render(request, 'communications/admin/article_form.html', {
        'form': form,
        'article': article,
        'title': 'Edit Article',
        'button_text': 'Update Article',
    })


@login_required
def admin_article_delete(request, slug):
    article = get_object_or_404(Article, slug=slug)
    if not request.user.has_perm('communications.delete_article'):
        messages.error(request, "Permission denied.")
        return redirect('communications:admin_article_list')

    if request.method == 'POST':
        title = article.title
        article.delete()
        messages.success(request, f"🗑️ Article '{title}' deleted.")
        return redirect('communications:admin_article_list')

    return render(request, 'communications/admin/article_confirm_delete.html', {'article': article})


# ============================================================
# SUBSCRIBERS ADMIN (LIST + EXPORT)
# ============================================================


@login_required
def admin_subscriber_list(request):
    if not request.user.has_perm('communications.view_subscriber'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    # Handle bulk actions
    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')

        if not ids:
            messages.warning(request, "No subscribers selected.")
        elif action == 'delete':
            if request.user.has_perm('communications.delete_subscriber'):
                count = Subscriber.objects.filter(id__in=ids).delete()[0]
                messages.success(request, f"🗑️ {count} subscriber(s) deleted.")
            else:
                messages.error(request, "Permission denied to delete subscribers.")
        elif action == 'mark_verified':
            if request.user.has_perm('communications.change_subscriber'):
                count = Subscriber.objects.filter(id__in=ids).update(is_verified=True)
                messages.success(request, f"✅ {count} subscriber(s) marked as verified.")
            else:
                messages.error(request, "Permission denied to update subscribers.")
        elif action == 'mark_unverified':
            if request.user.has_perm('communications.change_subscriber'):
                count = Subscriber.objects.filter(id__in=ids).update(is_verified=False)
                messages.success(request, f"✅ {count} subscriber(s) marked as unverified.")
            else:
                messages.error(request, "Permission denied to update subscribers.")
        elif action == 'activate':
            if request.user.has_perm('communications.change_subscriber'):
                count = Subscriber.objects.filter(id__in=ids).update(is_active=True)
                messages.success(request, f"✅ {count} subscriber(s) activated.")
            else:
                messages.error(request, "Permission denied to update subscribers.")
        elif action == 'deactivate':
            if request.user.has_perm('communications.change_subscriber'):
                count = Subscriber.objects.filter(id__in=ids).update(is_active=False)
                messages.success(request, f"✅ {count} subscriber(s) deactivated.")
            else:
                messages.error(request, "Permission denied to update subscribers.")

        return redirect('communications:admin_subscriber_list')

    # GET — list with filters
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')

    subscribers = Subscriber.objects.all().order_by('-subscribed_at')

    if query:
        subscribers = subscribers.filter(email__icontains=query)

    if status_filter == 'verified':
        subscribers = subscribers.filter(is_verified=True)
    elif status_filter == 'unverified':
        subscribers = subscribers.filter(is_verified=False)

    paginator = Paginator(subscribers, 30)
    page = request.GET.get('page')
    subscribers_page = paginator.get_page(page)

    return render(request, 'communications/admin/subscriber_list.html', {
        'subscribers': subscribers_page,
        'page_obj': subscribers_page,
        'is_paginated': subscribers_page.has_other_pages(),
        'query': query,
        'status_filter': status_filter,
    })


@login_required
def admin_subscriber_create(request):
    """Manually add a new subscriber."""
    if not request.user.has_perm('communications.add_subscriber'):
        messages.error(request, "Permission denied.")
        return redirect('communications:admin_subscriber_list')

    if request.method == 'POST':
        form = SubscriberForm(request.POST)
        if form.is_valid():
            subscriber = form.save(commit=False)
            if not subscriber.token:
                subscriber.token = uuid.uuid4()
            subscriber.save()
            messages.success(request, f"✅ Subscriber '{subscriber.email}' added.")
            return redirect('communications:admin_subscriber_list')
    else:
        form = SubscriberForm()

    return render(request, 'communications/admin/subscriber_form.html', {
        'form': form,
        'title': 'Add Subscriber',
        'button_text': 'Add Subscriber',
    })


@login_required
def admin_subscriber_edit(request, pk):
    """Edit an existing subscriber."""
    subscriber = get_object_or_404(Subscriber, pk=pk)
    if not request.user.has_perm('communications.change_subscriber'):
        messages.error(request, "Permission denied.")
        return redirect('communications:admin_subscriber_list')

    if request.method == 'POST':
        form = SubscriberForm(request.POST, instance=subscriber)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Subscriber '{subscriber.email}' updated.")
            return redirect('communications:admin_subscriber_list')
    else:
        form = SubscriberForm(instance=subscriber)

    return render(request, 'communications/admin/subscriber_form.html', {
        'form': form,
        'subscriber': subscriber,
        'title': 'Edit Subscriber',
        'button_text': 'Update Subscriber',
    })


@login_required
def admin_subscriber_delete(request, pk):
    """Delete a subscriber with confirmation."""
    subscriber = get_object_or_404(Subscriber, pk=pk)
    if not request.user.has_perm('communications.delete_subscriber'):
        messages.error(request, "Permission denied.")
        return redirect('communications:admin_subscriber_list')

    if request.method == 'POST':
        email = subscriber.email
        subscriber.delete()
        messages.success(request, f"🗑️ Subscriber '{email}' deleted.")
        return redirect('communications:admin_subscriber_list')

    return render(request, 'communications/admin/subscriber_confirm_delete.html', {
        'subscriber': subscriber,
    })


@login_required
def admin_subscriber_export(request):
    if not request.user.has_perm('communications.view_subscriber'):
        messages.error(request, "Permission denied.")
        return redirect('communications:admin_subscriber_list')

    spec = ImportSpec()
    spec.key = 'subscribers'
    spec.label = 'Subscribers'
    spec.columns = [
        ColumnSpec('email', 'Email'),
        ColumnSpec('is_verified', 'Verified'),
        ColumnSpec('is_active', 'Active'),
        ColumnSpec('subscribed_at', 'Subscribed At'),
        ColumnSpec('notify_announcements', 'Notify Announcements'),
        ColumnSpec('notify_events', 'Notify Events'),
        ColumnSpec('notify_prayer_changes', 'Notify Prayer Changes'),
    ]
    spec.model = Subscriber

    def export_queryset():
        return Subscriber.objects.all().order_by('email')

    def row_from_instance(sub):
        return {
            'email': sub.email,
            'is_verified': 'Yes' if sub.is_verified else 'No',
            'is_active': 'Yes' if sub.is_active else 'No',
            'subscribed_at': sub.subscribed_at.strftime('%Y-%m-%d %H:%M'),
            'notify_announcements': 'Yes' if sub.notify_announcements else 'No',
            'notify_events': 'Yes' if sub.notify_events else 'No',
            'notify_prayer_changes': 'Yes' if sub.notify_prayer_changes else 'No',
        }

    spec.export_queryset = export_queryset
    spec.row_from_instance = row_from_instance

    return build_export_xlsx(spec)


# ============================================================
# BROADCAST (CUSTOM EMAIL WITH FILTERING)
# ============================================================

@login_required
def admin_broadcast(request):
    if not (request.user.is_superuser or request.user.has_perm('communications.can_send_broadcast')):
        messages.error(request, "You don't have permission to send broadcasts.")
        return redirect('dashboards:dashboard')

    offices = Office.objects.all().order_by('name')
    recipients = []
    preview = False

    if request.method == 'POST':
        action = request.POST.get('action')
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()

        if action == 'preview':
            office_ids = request.POST.getlist('offices')
            status_filter = request.POST.get('status', 'current')
            gender_filter = request.POST.get('gender', 'all')
            type_filter = request.POST.get('type', 'all')
            specific_email = request.POST.get('specific_email', '').strip()
            recipients = _build_recipient_list(office_ids, status_filter, gender_filter, type_filter, specific_email)
            preview = True

        elif action == 'send':
            office_ids = request.POST.getlist('offices')
            status_filter = request.POST.get('status', 'current')
            gender_filter = request.POST.get('gender', 'all')
            type_filter = request.POST.get('type', 'all')
            specific_email = request.POST.get('specific_email', '').strip()

            if not subject or not body:
                messages.error(request, "Subject and body are required.")
                return redirect('communications:admin_broadcast')

            recipients = _build_recipient_list(office_ids, status_filter, gender_filter, type_filter, specific_email)

            if not recipients:
                messages.error(request, "No recipients found.")
                return redirect('communications:admin_broadcast')

            for email in recipients:
                send_templated_email(
                    subject=subject,
                    recipients=[email],
                    template_name='emails/broadcast.html',
                    context={'subject': subject, 'body': body},
                    category='broadcast'
                )
            messages.success(request, f"✅ Message sent to {len(recipients)} recipient(s).")
            return redirect('communications:admin_broadcast')

    return render(request, 'communications/admin/broadcast.html', {
        'offices': offices,
        'recipients': recipients,
        'preview': preview,
        'recipient_count': len(recipients),
    })


def _build_recipient_list(office_ids, status_filter, gender_filter, type_filter, specific_email):
    emails = set()

    if specific_email:
        emails.add(specific_email)
        return list(emails)

    users = User.objects.filter(is_active=True)

    if office_ids:
        users = users.filter(office_assignments__office_id__in=office_ids, office_assignments__is_active=True)

    if status_filter == 'current':
        users = users.filter(is_alumni=False)
    elif status_filter == 'alumni':
        users = users.filter(is_alumni=True)

    for user in users.distinct():
        if user.email:
            emails.add(user.email)

    if type_filter in ('subscribers', 'all'):
        subscribers = Subscriber.objects.filter(is_active=True, is_verified=True)
        for sub in subscribers:
            emails.add(sub.email)

    if type_filter in ('patrons', 'all'):
        from community.models import Patron
        patrons = Patron.objects.filter(is_active=True).exclude(email='')
        for patron in patrons:
            emails.add(patron.email)

    return list(emails)