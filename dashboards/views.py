from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import models, transaction
from django.db.models import Count, Q, Sum, F
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth.models import Permission
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from accounts.models import OfficeAssignment, Office, User
from core.dashboard_widgets import widgets_for_permissions
from namets_notifications.models import Notification

# --- Model imports for stats ---
from communications.models import (
    Announcement, PrayerSchedule, DonationCampaign,
    MagazineIssue, Article, Subscriber
)
from events.models import Event
from lostfound.models import Item
from gallery.models import Gallery
from community.models import (
    Patron, Executive, Developer, Question,
    TutorApplication, MembershipApplication,
    SocialMediaLink, NAMETSDocument
)


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render, redirect
from accounts.models import Department


from business.models import Transaction, ShopOrder, EquipmentBorrow, Booking, FreeClaim

from academics.models import (
    Course, Tutor, Session,
    IslamiyyaRegistration, UserResourceSubmission,
    TutorEvaluation, CompetitionResult,
    CBTCourse, QuestionBank,
)

# --- Messaging models ---
from dashboards.models import Message, MessageRecipient


# ============================================================
#  HELPER: Compute KPI Stats (dictionary for base_dashboard)
# ============================================================

def _get_kpi_stats(user):
    """
    Returns a dictionary of stats for the KPI cards in base_dashboard.html.
    Keys match those used in the template: announcements_count, events_count, etc.
    """
    stats = {}

    # Unread notifications (always shown)
    stats['unread_notifications'] = Notification.objects.filter(recipient=user, is_read=False).count()

    # Only add stats for models the user has permission to view
    if user.has_perm('communications.view_announcement'):
        stats['announcements_count'] = Announcement.objects.filter(is_active=True).count()
    if user.has_perm('events.view_event'):
        stats['events_count'] = Event.objects.filter(is_active=True).count()
    if user.has_perm('lostfound.view_item'):
        stats['lostfound_count'] = Item.objects.filter(is_active=True).count()
    if user.has_perm('gallery.view_gallery'):
        stats['gallery_count'] = Gallery.objects.count()
    if user.has_perm('community.view_patron'):
        stats['patrons_count'] = Patron.objects.filter(is_active=True).count()
    if user.has_perm('community.view_executive'):
        stats['executives_count'] = Executive.objects.filter(is_active=True).count()
    if user.has_perm('community.view_developer'):
        stats['developers_count'] = Developer.objects.filter(is_active=True).count()
    if user.has_perm('community.view_question'):
        stats['questions_pending'] = Question.objects.filter(is_public=False).count()
    if user.has_perm('community.view_tutorapplication'):
        stats['tutor_applications_pending'] = TutorApplication.objects.filter(is_processed=False).count()
    if user.has_perm('community.view_membershipapplication'):
        stats['membership_applications_pending'] = MembershipApplication.objects.filter(is_processed=False).count()
    if user.has_perm('communications.view_subscriber'):
        stats['subscribers_count'] = Subscriber.objects.filter(is_active=True).count()
    if user.has_perm('communications.view_prayerschedule'):
        stats['prayer_schedules_count'] = PrayerSchedule.objects.filter(is_active=True).count()
    if user.has_perm('communications.view_donationcampaign'):
        stats['donation_campaigns_count'] = DonationCampaign.objects.filter(is_active=True).count()
    if user.has_perm('communications.view_magazineissue'):
        stats['magazines_count'] = MagazineIssue.objects.filter(is_active=True).count()
    if user.has_perm('communications.view_article'):
        stats['articles_count'] = Article.objects.filter(is_active=True).count()
    if user.has_perm('community.view_socialmedialink'):
        stats['social_links_count'] = SocialMediaLink.objects.filter(is_active=True).count()
    if user.has_perm('community.view_nametsdocument'):
        stats['documents_count'] = NAMETSDocument.objects.filter(is_active=True).count()
    if user.has_perm('accounts.view_user') or user.has_perm('ict.view_user'):
        stats['users_count'] = User.objects.filter(is_active=True).count()

    # ===== BUSINESS APP =====
    if user.has_perm('business.view_transaction'):
        stats['transactions_count'] = Transaction.objects.count()
    if user.has_perm('business.view_shoporder'):
        stats['pending_shop_orders'] = ShopOrder.objects.filter(status='pending').count()
    if user.has_perm('business.view_equipmentborrow'):
        stats['overdue_borrows'] = EquipmentBorrow.objects.filter(
            status='borrowed',
            expected_return_date__lt=timezone.now()
        ).count()
    if user.has_perm('business.view_booking'):
        stats['pending_bookings'] = Booking.objects.filter(status='pending').count()
    if user.has_perm('business.view_freeclaim'):
        stats['pending_free_claims'] = FreeClaim.objects.filter(status='pending').count()

    # ===== ACADEMICS =====
    if user.has_perm('academics.view_course'):
        stats['courses_count'] = Course.objects.filter(is_active=True).count()
    if user.has_perm('academics.view_tutor'):
        stats['tutors_count'] = Tutor.objects.filter(is_active=True).count()
    if user.has_perm('academics.view_session'):
        stats['upcoming_sessions_count'] = Session.objects.filter(
            is_active=True,
            date__gte=timezone.now().date()
        ).count()
    if user.has_perm('academics.view_islamiyyaregistration'):
        stats['islamiyya_pending'] = IslamiyyaRegistration.objects.filter(
            payment_status='pending'
        ).count()
        stats['islamiyya_paid'] = IslamiyyaRegistration.objects.filter(
            payment_status='paid'
        ).count()
    if user.has_perm('academics.view_userresourcesubmission'):
        stats['pending_resources_count'] = UserResourceSubmission.objects.filter(
            status='pending'
        ).count()
    if user.has_perm('academics.view_tutorevaluation'):
        stats['tutor_evaluations_count'] = TutorEvaluation.objects.count()
    if user.has_perm('academics.view_competitionresult'):
        stats['competition_results_count'] = CompetitionResult.objects.filter(
            is_active=True
        ).count()

    # ===== CBT =====
    if user.has_perm('academics.view_cbtcourse'):
        stats['cbt_courses_count'] = CBTCourse.objects.filter(is_active=True).count()

    if user.has_perm('academics.view_questionbank'):
        qs_active = QuestionBank.objects.filter(is_active=True)
        stats['cbt_questions_count'] = qs_active.count()

        stats['cbt_questions_low_quality'] = qs_active.filter(
            times_answered__gte=5,
            times_correct__lt=F('times_answered') * 0.4,
        ).count()

        agg = QuestionBank.objects.aggregate(total=Sum('times_answered'))
        stats['cbt_attempts_total'] = agg['total'] or 0

    # ===== GOVERNANCE =====
    if user.has_perm('governance.view_task'):
        from governance.models import Task as GovTask
        my_open = GovTask.for_user(user, include_office=True).filter(
            status__in=['pending', 'in_progress']
        )
        stats['governance_my_open_tasks'] = my_open.count()
        stats['governance_my_overdue_tasks'] = my_open.filter(
            deadline__lt=timezone.now(),
            deadline__isnull=False,
        ).count()

    if user.has_perm('governance.view_proposal'):
        from governance.models import Proposal
        active = Proposal.objects.filter(status='voting')
        stats['governance_active_proposals'] = active.count()
        pending = 0
        for p in active:
            if p.user_can_vote(user):
                pending += 1
        stats['governance_pending_votes'] = pending

    if user.has_perm('governance.view_nominationintake'):
        from governance.models import NominationIntake
        stats['governance_pending_nominations'] = NominationIntake.objects.filter(
            status__in=['pending', 'shortlisted']
        ).count()

    return stats


# ============================================================
#  HELPER: Compute Mini Stats (list for office_dashboard)
# ============================================================

def _get_mini_stats(user, office=None):
    """
    Returns a list of stat items for the mini stats row in office_dashboard.html.
    Each item: {'icon': '📢', 'count': 5, 'label': 'Announcements'}
    """
    stats = []

    if user.has_perm('communications.view_announcement'):
        stats.append({
            'icon': '📢',
            'count': Announcement.objects.filter(is_active=True).count(),
            'label': 'Announcements'
        })

    if user.has_perm('events.view_event'):
        stats.append({
            'icon': '📅',
            'count': Event.objects.filter(is_active=True, start_datetime__gte=timezone.now()).count(),
            'label': 'Upcoming Events'
        })

    if user.has_perm('community.view_membershipapplication'):
        stats.append({
            'icon': '👥',
            'count': MembershipApplication.objects.filter(is_processed=False).count(),
            'label': 'Membership Apps (Pending)'
        })

    if user.has_perm('community.view_tutorapplication'):
        stats.append({
            'icon': '👨‍🏫',
            'count': TutorApplication.objects.filter(is_processed=False).count(),
            'label': 'Tutor Apps (Pending)'
        })

    if user.has_perm('lostfound.view_item'):
        stats.append({
            'icon': '🔍',
            'count': Item.objects.filter(is_active=True, status='lost').count(),
            'label': 'Lost Items'
        })

    if user.has_perm('communications.view_subscriber'):
        stats.append({
            'icon': '📧',
            'count': Subscriber.objects.filter(is_active=True).count(),
            'label': 'Subscribers'
        })

    if user.has_perm('community.view_question'):
        stats.append({
            'icon': '❓',
            'count': Question.objects.filter(is_public=False).count(),
            'label': 'Questions (Pending)'
        })

    # ===== BUSINESS APP =====
    if user.has_perm('business.view_transaction'):
        stats.append({
            'icon': '💰',
            'count': Transaction.objects.count(),
            'label': 'Transactions'
        })

    if user.has_perm('business.view_shoporder'):
        stats.append({
            'icon': '🛒',
            'count': ShopOrder.objects.filter(status='pending').count(),
            'label': 'Pending Orders'
        })

    if user.has_perm('business.view_equipmentborrow'):
        stats.append({
            'icon': '⏰',
            'count': EquipmentBorrow.objects.filter(
                status='borrowed',
                expected_return_date__lt=timezone.now()
            ).count(),
            'label': 'Overdue Equipment'
        })

    if user.has_perm('business.view_booking'):
        stats.append({
            'icon': '🎟️',
            'count': Booking.objects.filter(status='pending').count(),
            'label': 'Pending Bookings'
        })

    if user.has_perm('business.view_freeclaim'):
        stats.append({
            'icon': '🎁',
            'count': FreeClaim.objects.filter(status='pending').count(),
            'label': 'Pending Claims'
        })

    # ===== CBT (mini row) =====
    if user.has_perm('academics.view_questionbank'):
        stats.append({
            'icon': '🧠',
            'count': QuestionBank.objects.filter(is_active=True).count(),
            'label': 'CBT Questions'
        })

    # ===== GOVERNANCE (mini row) =====
    if user.has_perm('governance.view_task'):
        from governance.models import Task as GovTask
        stats.append({
            'icon': '✅',
            'count': GovTask.for_user(user, include_office=True).filter(
                status__in=['pending', 'in_progress']
            ).count(),
            'label': 'My Open Tasks'
        })

    if user.has_perm('governance.view_proposal'):
        from governance.models import Proposal
        active = Proposal.objects.filter(status='voting')
        pending = sum(1 for p in active if p.user_can_vote(user))
        stats.append({
            'icon': '🗳️',
            'count': pending,
            'label': 'Awaiting My Vote'
        })

    return stats


# ============================================================
#  HELPER: Office-wide task aggregation
# ============================================================
# "Office tasks" = any governance Task that touches this office, either:
#   • assigned_office == this office, OR
#   • assigned_to is an active member of this office
# ============================================================

def _get_office_task_stats(office):
    """Return counts of tasks related to this office."""
    empty = {'total': 0, 'open': 0, 'overdue': 0, 'completed': 0, 'cancelled': 0}
    if not office:
        return empty

    from governance.models import Task

    member_ids = list(
        OfficeAssignment.objects.filter(
            office=office, is_active=True
        ).values_list('user_id', flat=True)
    )

    qs = Task.objects.filter(
        Q(assigned_office=office) | Q(assigned_to_id__in=member_ids)
    ).distinct()

    open_qs = qs.filter(status__in=['pending', 'in_progress'])
    overdue_qs = open_qs.filter(
        deadline__lt=timezone.now(), deadline__isnull=False
    )

    return {
        'total': qs.count(),
        'open': open_qs.count(),
        'overdue': overdue_qs.count(),
        'completed': qs.filter(status='completed').count(),
        'cancelled': qs.filter(status='cancelled').count(),
    }


def _get_office_tasks(office, limit=15):
    """Return the most relevant tasks for this office (active first)."""
    if not office:
        return []

    from governance.models import Task

    member_ids = list(
        OfficeAssignment.objects.filter(
            office=office, is_active=True
        ).values_list('user_id', flat=True)
    )

    return list(
        Task.objects.filter(
            Q(assigned_office=office) | Q(assigned_to_id__in=member_ids)
        )
        .distinct()
        .select_related('assigned_to', 'assigned_office', 'assigned_by')
        .order_by('status', 'deadline', '-priority', '-created_at')[:limit]
    )





# ============================================================
#  RENDER OFFICE DASHBOARD (Helper)
# ============================================================

def _render_office_dashboard(request, assignment):
    """Helper function to render the actual dashboard."""
    office = assignment.office
    user = request.user

    permission_codenames = {
        f"{p.content_type.app_label}.{p.codename}"
        for p in assignment.office.permissions.all()
    }

    greeting_title = assignment.display_label or assignment.office.name

    manageable_offices = [
        o for o in Office.objects.exclude(pk=assignment.office.pk)
        if assignment.office.can_manage(o)
    ]
    can_manage_permissions = len(manageable_offices) > 0

    widgets = widgets_for_permissions(permission_codenames)

    kpi_stats = _get_kpi_stats(user)
    mini_stats = _get_mini_stats(user, office)

    # --- Office-wide task aggregation ---
    office_task_stats = _get_office_task_stats(office)
    office_tasks = _get_office_tasks(office, limit=15)

    from namets_notifications.models import ActivityLog
    recent_activity = ActivityLog.objects.select_related('user').order_by('-timestamp')[:10]

    context = {
        'assignment': assignment,
        'all_assignments': request.user.office_assignments.filter(is_active=True),
        'greeting_title': greeting_title,
        'widgets': widgets,
        'can_manage_permissions': can_manage_permissions,
        'kpi_stats': kpi_stats,
        'stats': mini_stats,
        'recent_activity': recent_activity,
        'office': office,
        # NEW:
        'office_task_stats': office_task_stats,
        'office_tasks': office_tasks,
    }

    return render(request, 'dashboards/office_dashboard.html', context)

# ============================================================
#  MAIN DASHBOARD VIEW
# ============================================================

@login_required
def dashboard(request):
    if getattr(request.user, 'is_alumni', False):
        return redirect('dashboards:alumni_dashboard')

    assignments = request.user.office_assignments.filter(is_active=True)

    if not assignments.exists():
        permission_codenames = {
            f"{p.content_type.app_label}.{p.codename}"
            for p in request.user.user_permissions.all()
        }
        widgets = widgets_for_permissions(permission_codenames)
        kpi_stats = _get_kpi_stats(request.user)
        mini_stats = []
        return render(request, 'dashboards/office_dashboard.html', {
            'assignment': None,
            'all_assignments': [],
            'greeting_title': None,
            'widgets': widgets,
            'can_manage_permissions': False,
            'kpi_stats': kpi_stats,
            'stats': mini_stats,
        })

    active_office_id = request.session.get('active_office_id')
    if assignments.count() == 1:
        assignment = assignments.first()
        request.session['active_office_id'] = assignment.office_id
        return _render_office_dashboard(request, assignment)

    if active_office_id:
        assignment = assignments.filter(office_id=active_office_id).first()
        if assignment:
            return _render_office_dashboard(request, assignment)
        else:
            del request.session['active_office_id']

    kpi_stats = _get_kpi_stats(request.user)
    return render(request, 'dashboards/choose_office.html', {
        'assignments': assignments,
        'kpi_stats': kpi_stats,
    })


# ============================================================
#  SWITCH OFFICE
# ============================================================

@login_required
def switch_office(request, assignment_id):
    assignment = get_object_or_404(request.user.office_assignments, id=assignment_id, is_active=True)
    request.session['active_office_id'] = assignment.office_id
    return redirect('dashboards:dashboard')


# ============================================================
#  MANAGE PERMISSIONS
# ============================================================

@login_required
def manage_permissions(request):
    my_assignment = request.user.office_assignments.filter(is_active=True).first()
    if not my_assignment:
        messages.error(request, "You don't hold an office.")
        return redirect('dashboards:dashboard')

    my_office = my_assignment.office
    manageable_offices = [
        o for o in Office.objects.exclude(pk=my_office.pk)
        if my_office.can_manage(o)
    ]

    if request.method == 'POST':
        target_assignment = get_object_or_404(
            OfficeAssignment, id=request.POST['assignment_id'], is_active=True
        )
        if not my_office.can_manage(target_assignment.office):
            messages.error(request, "You don't have permission to manage that office.")
            return redirect('dashboards:manage_permissions')

        allowed_ids = set(my_office.permissions.values_list('id', flat=True))
        requested_ids = set(int(pid) for pid in request.POST.getlist('permissions'))
        to_grant = requested_ids & allowed_ids

        current_perms = set(target_assignment.user.user_permissions.values_list('id', flat=True))
        new_perms = (current_perms - allowed_ids) | to_grant
        target_assignment.user.user_permissions.set(Permission.objects.filter(id__in=new_perms))

        messages.success(request, f"Updated permissions for {target_assignment.user.get_full_name()}.")
        return redirect('dashboards:manage_permissions')

    target_assignments = OfficeAssignment.objects.filter(
        office__in=manageable_offices, is_active=True
    ).select_related('user', 'office')

    return render(request, 'dashboards/manage_permissions.html', {
        'my_office': my_office,
        'available_permissions': my_office.permissions.all(),
        'target_assignments': target_assignments,
    })


# ============================================================
#  REASSIGN OFFICE (Staff only)
# ============================================================

@staff_member_required
def reassign_office(request):
    if request.method == 'POST':
        old_assignment = get_object_or_404(OfficeAssignment, id=request.POST['assignment_id'], is_active=True)
        new_office = get_object_or_404(Office, id=request.POST['new_office_id'])

        old_assignment.is_active = False
        old_assignment.save(update_fields=['is_active'])

        OfficeAssignment.objects.create(
            user=old_assignment.user,
            office=new_office,
            display_label=request.POST.get('display_label', ''),
        )
        messages.success(
            request,
            f"{old_assignment.user.get_full_name()} moved from {old_assignment.office.name} to {new_office.name}."
        )
        return redirect('dashboards:reassign_office')

    active_assignments = OfficeAssignment.objects.filter(is_active=True).select_related('user', 'office')
    offices = Office.objects.all()
    return render(request, 'dashboards/reassign_office.html', {
        'active_assignments': active_assignments,
        'offices': offices,
    })


# ============================================================
#  OFFICE DIRECTORY
# ============================================================

def office_directory(request):
    offices = Office.objects.all().order_by('name')
    return render(request, 'dashboards/offices_directory.html', {'offices': offices})


# ============================================================
#  ACTIVITY LOG
# ============================================================

@login_required
def activity_log(request):
    from namets_notifications.models import ActivityLog

    logs = ActivityLog.objects.select_related('user').order_by('-timestamp')

    user_id = request.GET.get('user')
    if user_id:
        logs = logs.filter(user_id=user_id)

    action = request.GET.get('action')
    if action:
        logs = logs.filter(action=action)

    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    users = User.objects.filter(is_active=True).order_by('username')

    return render(request, 'dashboards/activity_log.html', {
        'page_obj': page_obj,
        'users': users,
        'selected_user': user_id,
        'selected_action': action,
    })


# ============================================================
#  NOTIFICATIONS INBOX (system alerts — unchanged)
# ============================================================

@login_required
def inbox(request):
    """The notification inbox — shows system-generated notifications (bell)."""
    filter_type = request.GET.get("type", "all")
    qs = Notification.objects.filter(recipient=request.user)
    if filter_type != "all":
        qs = qs.filter(notification_type=filter_type)
    qs = qs.order_by('-created_at')
    return render(request, 'dashboards/inbox.html', {
        'notifications': qs[:100],
        'unread_count': Notification.objects.filter(recipient=request.user, is_read=False).count(),
        'notification_types': Notification.Type.choices,
        'current_filter': filter_type,
    })


@require_POST
@login_required
def inbox_mark_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notif.mark_read()
    return redirect(request.POST.get("next", "dashboards:inbox"))


@require_POST
@login_required
def inbox_mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return redirect('dashboards:inbox')


@login_required
def unread_count_api(request):
    """Bell icon count — notifications only."""
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'count': count})


# ============================================================
# ALUMNI DASHBOARD
# ============================================================

@login_required
def alumni_dashboard(request):
    """Dedicated alumni home page."""
    if not request.user.is_alumni:
        messages.info(request, "This area is for alumni only.")
        return redirect('dashboards:dashboard')

    profile = None
    try:
        profile = request.user.graduation_profile
    except Exception:
        profile = None

    from django.contrib.auth import get_user_model
    AuthUser = get_user_model()

    total_alumni = AuthUser.objects.filter(is_alumni=True, is_active=True).count()
    total_active_exco = AuthUser.objects.filter(
        is_alumni=False,
        is_active=True,
        office_assignments__is_active=True,
    ).distinct().count()

    current_year = timezone.now().year
    this_year_alumni = AuthUser.objects.filter(
        is_alumni=True,
        year_of_graduation=current_year,
    ).count()

    recent_alumni = AuthUser.objects.filter(
        is_alumni=True, is_active=True,
    ).exclude(pk=request.user.pk).order_by(
        '-year_of_graduation', 'first_name'
    )[:8]

    session_docs = []
    session_docs_count = 0
    try:
        from governance.models import SessionDocument
        session_docs = SessionDocument.objects.filter(
            is_published=True
        ).order_by('-session_year', 'order', '-uploaded_at')[:4]
        session_docs_count = SessionDocument.objects.filter(
            is_published=True
        ).count()
    except Exception:
        pass

    recent_proposals = []
    try:
        from governance.models import Proposal
        recent_proposals = Proposal.objects.filter(
            status__in=['passed', 'rejected', 'voting']
        ).order_by('-created_at')[:5]
    except Exception:
        pass

    return render(request, 'dashboards/alumni_dashboard.html', {
        'profile': profile,
        'total_alumni': total_alumni,
        'total_active_exco': total_active_exco,
        'this_year_alumni': this_year_alumni,
        'recent_alumni': recent_alumni,
        'session_docs': session_docs,
        'session_docs_count': session_docs_count,
        'recent_proposals': recent_proposals,
    })


@login_required
def alumni_directory(request):
    """Searchable contact directory."""
    is_alumni = getattr(request.user, 'is_alumni', False)
    has_active_office = request.user.office_assignments.filter(is_active=True).exists()

    if not (is_alumni or has_active_office or request.user.is_superuser):
        messages.error(request, "Directory access requires membership.")
        return redirect('dashboards:dashboard')

    from django.contrib.auth import get_user_model
    AuthUser = get_user_model()

    qs = AuthUser.objects.filter(is_active=True).order_by('first_name', 'last_name')

    q = request.GET.get('q', '').strip()
    filter_type = request.GET.get('type', '')
    dept_filter = request.GET.get('dept', '')

    if q:
        qs = qs.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(middle_name__icontains=q)
            | Q(email__icontains=q)
            | Q(phone_number__icontains=q)
        )

    if filter_type == 'alumni':
        qs = qs.filter(is_alumni=True)
    elif filter_type == 'exco':
        qs = qs.filter(
            is_alumni=False,
            office_assignments__is_active=True,
        ).distinct()

    if dept_filter:
        qs = qs.filter(department_id=dept_filter)

    page = Paginator(qs, 40).get_page(request.GET.get('page'))

    departments = Department.objects.all().order_by('name')

    total_people = AuthUser.objects.filter(is_active=True).count()
    alumni_count = AuthUser.objects.filter(is_alumni=True, is_active=True).count()
    exco_count = AuthUser.objects.filter(
        is_alumni=False, is_active=True,
        office_assignments__is_active=True,
    ).distinct().count()

    return render(request, 'dashboards/alumni_directory.html', {
        'users': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'q': q,
        'filter_type': filter_type,
        'dept_filter': dept_filter,
        'departments': departments,
        'total_people': total_people,
        'alumni_count': alumni_count,
        'exco_count': exco_count,
    })


# ============================================================
# MESSAGING (user-to-user — new section)
# ============================================================
# Separate from Notifications. The bell shows notifications.
# The envelope icon shows messages. Clean separation.

def _user_can_pin_message(user):
    """Wakeel, ICT, staff, superuser can pin messages."""
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return (
        user.office_assignments.filter(
            is_active=True, office__name__icontains='wakeel'
        ).exists()
        or user.office_assignments.filter(
            is_active=True, office__name__icontains='ict'
        ).exists()
    )


def _message_counts(user):
    return {
        'unread_count': MessageRecipient.objects.filter(
            user=user, is_read=False, is_deleted=False
        ).count(),
        'total_count': MessageRecipient.objects.filter(
            user=user, is_deleted=False
        ).count(),
        'sent_count': Message.objects.filter(sender=user).count(),
    }


@login_required
def messages_inbox(request):
    """Received messages (user-to-user)."""
    qs = MessageRecipient.objects.filter(
        user=request.user,
        is_deleted=False,
    ).select_related('message', 'message__sender').order_by(
        '-message__is_pinned', '-message__sent_at'
    )

    filter_type = request.GET.get('filter', 'all').strip()
    q = request.GET.get('q', '').strip()

    if filter_type == 'unread':
        qs = qs.filter(is_read=False)
    elif filter_type == 'pinned':
        qs = qs.filter(message__is_pinned=True)

    if q:
        qs = qs.filter(
            Q(message__subject__icontains=q)
            | Q(message__body__icontains=q)
            | Q(message__sender__first_name__icontains=q)
            | Q(message__sender__last_name__icontains=q)
            | Q(message__sender__email__icontains=q)
        )

    page = Paginator(qs, 25).get_page(request.GET.get('page'))

    return render(request, 'dashboards/messages.html', {
        'messages': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'filter_type': filter_type,
        'q': q,
        'tab': 'inbox',
        **_message_counts(request.user),
    })


@login_required
def messages_sent(request):
    """Messages the current user has sent."""
    qs = Message.objects.filter(sender=request.user).order_by('-sent_at')

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(subject__icontains=q)
            | Q(body__icontains=q)
            | Q(target_label__icontains=q)
        )

    page = Paginator(qs, 25).get_page(request.GET.get('page'))

    return render(request, 'dashboards/messages_sent.html', {
        'messages': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'q': q,
        'tab': 'sent',
        **_message_counts(request.user),
    })


@login_required
def message_detail(request, pk):
    """View a single message."""
    msg = get_object_or_404(
        Message.objects.select_related('sender').prefetch_related('recipients'),
        pk=pk,
    )

    is_sender = (msg.sender_id == request.user.id)
    recipient = None

    if not is_sender:
        recipient = msg.recipients.filter(
            user=request.user, is_deleted=False
        ).first()
        if not recipient:
            messages.error(request, "You don't have access to this message.")
            return redirect('dashboards:messages')

        if not recipient.is_read:
            recipient.is_read = True
            recipient.read_at = timezone.now()
            recipient.save(update_fields=['is_read', 'read_at'])

    return render(request, 'dashboards/message_detail.html', {
        'message': msg,
        'recipient': recipient,
        'is_sender': is_sender,
        'can_pin': _user_can_pin_message(request.user),
        **_message_counts(request.user),
    })


@login_required
def message_compose(request):
    """Compose a new message."""
    if request.method == 'POST':
        subject = (request.POST.get('subject') or '').strip()
        body = (request.POST.get('body') or '').strip()
        target_type = (request.POST.get('target_type') or 'current').strip()

        errors = []
        if not subject:
            errors.append("Subject is required.")
        if not body:
            errors.append("Message body is required.")
        if target_type not in dict(Message.TARGET_CHOICES):
            errors.append("Invalid target.")

        recipients_qs = User.objects.none()
        target_label = ''

        if target_type == 'direct':
            user_ids = request.POST.getlist('user_ids')
            if not user_ids:
                errors.append("Please select at least one person.")
            else:
                recipients_qs = User.objects.filter(pk__in=user_ids, is_active=True)
                n = recipients_qs.count()
                target_label = f"{n} selected {'person' if n == 1 else 'people'}"
        elif target_type == 'offices':
            office_ids = request.POST.getlist('office_ids')
            if not office_ids:
                errors.append("Please select at least one office.")
            else:
                offices = list(Office.objects.filter(pk__in=office_ids).values_list('name', flat=True))
                target_label = ', '.join(offices)[:200]
                recipients_qs = User.objects.filter(
                    office_assignments__office_id__in=office_ids,
                    office_assignments__is_active=True,
                    is_active=True,
                ).distinct()
        elif target_type == 'current':
            recipients_qs = User.objects.filter(is_alumni=False, is_active=True)
            target_label = 'All current members'
        elif target_type == 'alumni':
            recipients_qs = User.objects.filter(is_alumni=True, is_active=True)
            target_label = 'All alumni'
        elif target_type == 'everyone':
            recipients_qs = User.objects.filter(is_active=True)
            target_label = 'Everyone'

        recipients_qs = recipients_qs.exclude(pk=request.user.pk)

        if not errors and not recipients_qs.exists():
            errors.append("No recipients matched your selection.")

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            with transaction.atomic():
                new_msg = Message.objects.create(
                    sender=request.user,
                    subject=subject,
                    body=body,
                    target_type=target_type,
                    target_label=target_label,
                )
                MessageRecipient.objects.bulk_create([
                    MessageRecipient(message=new_msg, user=u)
                    for u in recipients_qs
                ])
            n = new_msg.recipients.count()
            messages.success(
                request,
                f"✅ Message sent to {n} {'person' if n == 1 else 'people'}."
            )
            return redirect('dashboards:messages_sent')

    # --- GET ---
    prefill_to = (request.GET.get('to') or '').strip()
    prefill_subject = (request.GET.get('subject') or '').strip()
    prefill_body = (request.GET.get('body') or '').strip()

    preselected_user_ids = []
    if prefill_to.isdigit():
        preselected_user_ids.append(int(prefill_to))

    default_target = 'direct' if preselected_user_ids else 'current'

    all_users = User.objects.filter(is_active=True).order_by(
        'first_name', 'last_name', 'email'
    )
    all_offices = Office.objects.all().order_by('name')

    return render(request, 'dashboards/message_compose.html', {
        'all_users': all_users,
        'all_offices': all_offices,
        'preselected_user_ids': preselected_user_ids,
        'prefill_subject': prefill_subject,
        'prefill_body': prefill_body,
        'default_target': default_target,
        'target_choices': Message.TARGET_CHOICES,
        **_message_counts(request.user),
    })


@login_required
@require_POST
def message_delete(request, pk):
    """Delete a message (sender hard-deletes; recipient soft-deletes)."""
    msg = get_object_or_404(Message, pk=pk)

    if msg.sender_id == request.user.id:
        msg.delete()
        messages.success(request, "Message deleted.")
        return redirect('dashboards:messages_sent')

    rec = msg.recipients.filter(user=request.user, is_deleted=False).first()
    if not rec:
        messages.error(request, "You don't have access to this message.")
        return redirect('dashboards:messages')

    rec.is_deleted = True
    rec.save(update_fields=['is_deleted'])
    messages.success(request, "Message removed from your inbox.")
    return redirect('dashboards:messages')


@login_required
@require_POST
def message_toggle_pin(request, pk):
    """Pin/unpin a message (admins only)."""
    if not _user_can_pin_message(request.user):
        messages.error(request, "Only admins can pin messages.")
        return redirect('dashboards:messages')

    msg = get_object_or_404(Message, pk=pk)
    msg.is_pinned = not msg.is_pinned
    msg.save(update_fields=['is_pinned'])

    messages.success(request, "📌 Message pinned." if msg.is_pinned else "Message unpinned.")
    return redirect('dashboards:message_detail', pk=msg.pk)


@login_required
def messages_unread_api(request):
    """JSON endpoint for the topbar envelope icon."""
    count = MessageRecipient.objects.filter(
        user=request.user, is_read=False, is_deleted=False
    ).count()
    return JsonResponse({'count': count})