
from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count, F
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from accounts.models import Office, OfficeAssignment, User
from .models import (
    AuditLog, Task, Proposal, Vote,
    NominationIntake, SelectionRecord, OathAcknowledgment,
    HandoverLog, GraduationProfile, SessionDocument
)

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.utils import timezone

from governance.models import GraduationProfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

# ============================================================
# 1. HELPERS
# ============================================================

try:
    from core.email_utils import send_email_with_fallback
    EMAIL_AVAILABLE = True
except Exception:
    EMAIL_AVAILABLE = False


def _client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '') or None


def _client_ua(request):
    return request.META.get('HTTP_USER_AGENT', '')[:300]


def log_audit(request, action, *, office=None, target_model='',
              target_id=None, object_repr='', changes=None):
    """
    Write an AuditLog entry. Safe to call from anywhere — never raises.
    """
    try:
        AuditLog.objects.create(
            user=request.user if getattr(request, 'user', None) and request.user.is_authenticated else None,
            action=action,
            office=office,
            target_model=target_model,
            target_id=target_id,
            object_repr=object_repr[:300] if object_repr else '',
            changes=changes or {},
            ip_address=_client_ip(request),
            user_agent=_client_ua(request),
        )
    except Exception:
        pass  # audit logging should never break a view


# ============================================================
# NOTIFICATION HELPERS
# ============================================================

def _notify(user, notification_type, title, message, admin_link=''):
    """
    Create an in-app Notification for a single user.
    Never raises — notification failure should never break a view.
    """
    if not user or not getattr(user, 'is_authenticated', True):
        return
    try:
        from namets_notifications.models import Notification
        Notification.objects.create(
            recipient=user,
            notification_type=notification_type,
            title=title[:255],
            message=message,
            admin_link=admin_link[:500],
        )
    except Exception:
        pass


def _notify_many(users, notification_type, title, message, admin_link=''):
    """Notify a list/queryset of users. Skips duplicates."""
    seen = set()
    for u in users:
        if not u or u.id in seen:
            continue
        seen.add(u.id)
        _notify(u, notification_type, title, message, admin_link)


def _notify_office(office, notification_type, title, message, admin_link=''):
    """Notify every active member of an office."""
    if not office:
        return
    try:
        members = User.objects.filter(
            office_assignments__office=office,
            office_assignments__is_active=True,
            is_active=True,
        ).distinct()
        _notify_many(members, notification_type, title, message, admin_link)
    except Exception:
        pass



def _user_offices(user):
    """Return the offices this user actively holds."""
    return Office.objects.filter(
        officeassignment__user=user,
        officeassignment__is_active=True,
    ).distinct()

def _user_primary_office(user):
    """First active office, for scoping."""
    return _user_offices(user).first()


def _can_view_all_audit(user):
    """Full audit log visibility — Wakeel, ICT Head, or superuser."""
    if user.is_superuser:
        return True
    if user.office_assignments.filter(
        is_active=True,
        office__is_protected=True,
    ).exists():
        return True  # ICT Head
    # Wakeel office
    return user.office_assignments.filter(
        is_active=True,
        office__name__icontains='wakeel',
    ).exists()


def _is_wakeel_or_ict(user):
    """Can execute handover, close proposals, etc."""
    return _can_view_all_audit(user)


def _send_email(subject, message, recipients, category='general', html_message=None):
    """Fire-and-forget email. Never raises."""
    if not EMAIL_AVAILABLE:
        return
    recipients = [r for r in recipients if r]
    if not recipients:
        return
    try:
        send_email_with_fallback(
            subject=subject,
            message=message,
            recipient_list=recipients,
            html_message=html_message,
            category=category,
        )
    except Exception:
        pass


# ============================================================
# 2. DASHBOARD
# ============================================================

@login_required
def governance_dashboard(request):
    """Main governance overview — tasks, proposals, recent audit."""
    if not request.user.has_perm('governance.view_task'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    user = request.user
    office = _user_primary_office(user)
    can_see_all = _can_view_all_audit(user)

    # ---- Tasks ----
    my_tasks_qs = Task.for_user(user, include_office=True)
    open_tasks = my_tasks_qs.filter(status__in=['pending', 'in_progress'])
    overdue_tasks = open_tasks.filter(
        deadline__lt=timezone.now(),
        deadline__isnull=False,
    )
    completed_this_week = my_tasks_qs.filter(
        status='completed',
        completed_at__gte=timezone.now() - timedelta(days=7),
    )

    # ---- Proposals ----
    active_proposals = Proposal.objects.filter(status='voting').order_by('voting_end')
    pending_votes = []
    for p in active_proposals:
        if p.user_can_vote(user):
            pending_votes.append(p)

    my_proposals = Proposal.objects.filter(proposed_by=user).order_by('-created_at')[:5]

    # ---- Audit (recent) ----
    audit_qs = AuditLog.objects.select_related('user', 'office')
    if not can_see_all and office:
        audit_qs = audit_qs.filter(office=office)
    recent_audit = audit_qs[:8]

    # ---- Nominations (if applicable) ----
    recent_nominations = NominationIntake.objects.filter(
        status__in=['pending', 'shortlisted']
    ).order_by('-created_at')[:5] if can_see_all else []

    return render(request, 'governance/dashboard.html', {
        'office': office,
        'open_tasks_count': open_tasks.count(),
        'overdue_tasks_count': overdue_tasks.count(),
        'completed_this_week': completed_this_week.count(),
        'active_proposals_count': active_proposals.count(),
        'pending_votes_count': len(pending_votes),
        'pending_votes': pending_votes[:3],
        'my_proposals': my_proposals,
        'recent_audit': recent_audit,
        'recent_nominations': recent_nominations,
        'recent_tasks': open_tasks.order_by('deadline', '-priority')[:5],
        'can_see_all_audit': can_see_all,
        'is_wakeel_or_ict': _is_wakeel_or_ict(user),
    })


# ============================================================
# 3. TASKS
# ============================================================

@login_required
def task_list(request):
    """All tasks visible to this user (own + office-wide)."""
    if not request.user.has_perm('governance.view_task'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    user = request.user
    can_see_all = _is_wakeel_or_ict(user)

    if can_see_all:
        qs = Task.objects.select_related('assigned_to', 'assigned_office', 'assigned_by')
    else:
        qs = Task.for_user(user, include_office=True).select_related(
            'assigned_to', 'assigned_office', 'assigned_by'
        )

    # Filters
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    assignee_filter = request.GET.get('assignee', '')
    scope_filter = request.GET.get('scope', '')  # mine / office / all
    query = request.GET.get('q', '').strip()

    if status_filter:
        qs = qs.filter(status=status_filter)
    if priority_filter:
        qs = qs.filter(priority=priority_filter)
    if assignee_filter == 'me':
        qs = qs.filter(assigned_to=user)
    elif assignee_filter == 'others':
        qs = qs.exclude(assigned_to=user)
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(description__icontains=query))

    # Overdue filter (simple boolean)
    if request.GET.get('overdue') == '1':
        qs = qs.filter(
            status__in=['pending', 'in_progress'],
            deadline__lt=timezone.now(),
        )

    qs = qs.order_by('status', 'deadline', '-priority', '-created_at')
    page = Paginator(qs, 30).get_page(request.GET.get('page'))

    # Counts for the top stats
    stats = {
        'total': qs.count(),
        'overdue': qs.filter(
            status__in=['pending', 'in_progress'],
            deadline__lt=timezone.now(),
        ).count() if request.GET.get('overdue') != '1' else qs.count(),
        'completed': qs.filter(status='completed').count(),
    }

    return render(request, 'governance/task_list.html', {
        'tasks': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'assignee_filter': assignee_filter,
        'query': query,
        'stats': stats,
        'can_see_all': can_see_all,
        'show_overdue_only': request.GET.get('overdue') == '1',
    })


@login_required
def task_detail(request, pk):
    if not request.user.has_perm('governance.view_task'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    task = get_object_or_404(
        Task.objects.select_related('assigned_to', 'assigned_office', 'assigned_by'),
        pk=pk
    )

    # Visibility check
    if not _is_wakeel_or_ict(request.user):
        visible = (
            task.assigned_to_id == request.user.id
            or task.assigned_office_id in _user_offices(request.user).values_list('id', flat=True)
            or task.assigned_by_id == request.user.id
        )
        if not visible:
            messages.error(request, "You don't have access to this task.")
            return redirect('governance:task_list')

    return render(request, 'governance/task_detail.html', {'task': task})


@login_required
def task_create(request):
    if not request.user.has_perm('governance.add_task'):
        messages.error(request, "Permission denied.")
        return redirect('governance:task_list')

    from .forms import TaskForm
    if request.method == 'POST':
        form = TaskForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.assigned_by = request.user
            task.save()

            log_audit(request, 'create',
                      target_model='Task', target_id=task.pk,
                      object_repr=task.title,
                      changes={'assigned_to': task.assignee_display,
                               'deadline': task.deadline.isoformat() if task.deadline else None})

            # ---- Notification ----
            link = reverse('governance:task_detail', args=[task.pk])
            deadline_str = task.deadline.strftime('%b %d, %Y %H:%M') if task.deadline else 'No deadline'
            body = (
                f"Priority: {task.get_priority_display()}\n"
                f"Deadline: {deadline_str}\n\n"
                f"{task.description[:200]}"
            )

            if task.assigned_to:
                # Personal task
                _notify(
                    task.assigned_to,
                    'task',
                    f"New task assigned: {task.title}",
                    f"From {request.user.get_full_name()}\n\n{body}",
                    link,
                )
                _send_email(
                    subject=f"[NAMETS] New task assigned: {task.title}",
                    message=(
                        f"Assalamu Alaikum {task.assigned_to.get_full_name()},\n\n"
                        f"You have a new task: {task.title}\n"
                        f"Priority: {task.get_priority_display()}\n"
                        f"Deadline: {deadline_str}\n\n"
                        f"View it on your dashboard."
                    ),
                    recipients=[task.assigned_to.email],
                    category='task',
                )
            elif task.assigned_office:
                # Office-wide task
                _notify_office(
                    task.assigned_office,
                    'task',
                    f"New office task: {task.title}",
                    f"Assigned to your office: {task.assigned_office.name}\n\n{body}",
                    link,
                )

            messages.success(request, f"✅ Task “{task.title}” created.")
            return redirect('governance:task_detail', pk=task.pk)
        messages.error(request, "Please fix the errors below.")
    else:
        form = TaskForm(user=request.user)

    return render(request, 'governance/task_form.html', {
        'form': form,
        'title': 'Create Task',
        'button_text': 'Create Task',
    })

@login_required
def task_edit(request, pk):
    if not request.user.has_perm('governance.change_task'):
        messages.error(request, "Permission denied.")
        return redirect('governance:task_list')

    task = get_object_or_404(Task, pk=pk)
    from .forms import TaskForm

    if request.method == 'POST':
        form = TaskForm(request.POST, request.FILES, instance=task, user=request.user)
        if form.is_valid():
            form.save()
            log_audit(request, 'update',
                      target_model='Task', target_id=task.pk,
                      object_repr=task.title)
            messages.success(request, "✅ Task updated.")
            return redirect('governance:task_detail', pk=task.pk)
        messages.error(request, "Please fix the errors below.")
    else:
        form = TaskForm(instance=task, user=request.user)

    return render(request, 'governance/task_form.html', {
        'form': form,
        'task': task,
        'title': f'Edit Task — {task.title[:40]}',
        'button_text': 'Save Changes',
    })


@require_POST
@login_required
def task_delete(request, pk):
    if not request.user.has_perm('governance.delete_task'):
        messages.error(request, "Permission denied.")
        return redirect('governance:task_list')

    task = get_object_or_404(Task, pk=pk)
    title = task.title
    task.delete()
    log_audit(request, 'delete', target_model='Task',
              target_id=pk, object_repr=title)
    messages.success(request, f"🗑️ Task “{title}” deleted.")
    return redirect('governance:task_list')


@require_POST
@login_required
def task_mark_complete(request, pk):
    """Mark a task complete (with optional proof)."""
    task = get_object_or_404(Task, pk=pk)

    can_complete = (
        task.assigned_to_id == request.user.id
        or task.assigned_office_id in _user_offices(request.user).values_list('id', flat=True)
        or _is_wakeel_or_ict(request.user)
        or request.user.has_perm('governance.change_task')
    )
    if not can_complete:
        messages.error(request, "You can't complete this task.")
        return redirect('governance:task_list')

    if task.status == 'completed':
        messages.info(request, "Task is already completed.")
        return redirect('governance:task_detail', pk=task.pk)

    proof = request.FILES.get('completion_proof')
    task.mark_completed(request.user, proof=proof)

    log_audit(request, 'update', target_model='Task',
              target_id=task.pk, object_repr=task.title,
              changes={'status': 'completed'})

    # ---- Notification: tell the creator ----
    if task.assigned_by and task.assigned_by_id != request.user.id:
        _notify(
            task.assigned_by,
            'task',
            f"Task completed: {task.title}",
            f"Marked complete by {request.user.get_full_name() or request.user.email}.",
            reverse('governance:task_detail', args=[task.pk]),
        )

    messages.success(request, f"✅ Task “{task.title}” marked completed.")
    return redirect('governance:task_detail', pk=task.pk)


@require_POST
@login_required
def task_bulk_action(request):
    if not request.user.has_perm('governance.change_task'):
        messages.error(request, "Permission denied.")
        return redirect('governance:task_list')

    action = request.POST.get('bulk_action', '')
    ids = request.POST.getlist('selected_ids')
    if not ids:
        messages.warning(request, "No tasks selected.")
        return redirect('governance:task_list')

    qs = Task.objects.filter(id__in=ids)

    if action == 'complete':
        n = 0
        for t in qs:
            if t.status != 'completed':
                t.mark_completed(request.user)
                # ---- Notification ----
                if t.assigned_by and t.assigned_by_id != request.user.id:
                    _notify(
                        t.assigned_by,
                        'task',
                        f"Task completed: {t.title}",
                        f"Marked complete by {request.user.get_full_name() or request.user.email}.",
                        reverse('governance:task_detail', args=[t.pk]),
                    )
                n += 1
        messages.success(request, f"✅ {n} task(s) completed.")
    elif action == 'in_progress':
        n = qs.update(status='in_progress', updated_at=timezone.now())
        messages.success(request, f"{n} task(s) set to In Progress.")
    elif action == 'cancel':
        n = qs.update(status='cancelled', updated_at=timezone.now())
        messages.success(request, f"{n} task(s) cancelled.")
    elif action == 'delete' and request.user.has_perm('governance.delete_task'):
        n, _ = qs.delete()
        messages.success(request, f"🗑️ {n} task(s) deleted.")
    else:
        messages.error(request, "Invalid action.")
        return redirect('governance:task_list')

    log_audit(request, 'update', target_model='Task', object_repr=f'Bulk {action}',
              changes={'count': len(ids)})
    return redirect('governance:task_list')

# ============================================================
# 4. PROPOSALS & VOTING
# ============================================================

@login_required
def proposal_list(request):
    if not request.user.has_perm('governance.view_proposal'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    qs = Proposal.objects.select_related('proposed_by').order_by('-created_at')

    status_filter = request.GET.get('status', '')
    proposer_filter = request.GET.get('proposer', '')
    query = request.GET.get('q', '').strip()
    show_mine = request.GET.get('mine') == '1'
    show_pending_vote = request.GET.get('pending_vote') == '1'

    if status_filter:
        qs = qs.filter(status=status_filter)
    if proposer_filter == 'me':
        qs = qs.filter(proposed_by=request.user)
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(description__icontains=query))
    if show_mine:
        qs = qs.filter(proposed_by=request.user)

    if show_pending_vote:
        active_ids = [p.pk for p in Proposal.objects.filter(status='voting') if p.user_can_vote(request.user)]
        qs = qs.filter(pk__in=active_ids)

    page = Paginator(qs, 20).get_page(request.GET.get('page'))

    # Enrich with tally
    proposals_with_tally = []
    for p in page:
        proposals_with_tally.append({
            'p': p,
            'tally': p.tally(),
            'can_vote': p.user_can_vote(request.user),
            'has_voted': p.votes.filter(voter=request.user).exists(),
        })

    return render(request, 'governance/proposal_list.html', {
        'proposals': proposals_with_tally,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'status_filter': status_filter,
        'proposer_filter': proposer_filter,
        'query': query,
        'show_mine': show_mine,
        'show_pending_vote': show_pending_vote,
    })


@login_required
def proposal_detail(request, pk):
    if not request.user.has_perm('governance.view_proposal'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    proposal = get_object_or_404(Proposal.objects.select_related('proposed_by'), pk=pk)
    votes = proposal.votes.select_related('voter').order_by('-cast_at')
    my_vote = votes.filter(voter=request.user).first()

    return render(request, 'governance/proposal_detail.html', {
        'proposal': proposal,
        'votes': votes,
        'my_vote': my_vote,
        'tally': proposal.tally(),
        'can_vote': proposal.user_can_vote(request.user),
        'is_owner': proposal.proposed_by_id == request.user.id,
        'is_wakeel_or_ict': _is_wakeel_or_ict(request.user),
    })


@login_required
def proposal_create(request):
    if not request.user.has_perm('governance.add_proposal'):
        messages.error(request, "Permission denied.")
        return redirect('governance:proposal_list')

    from .forms import ProposalForm
    if request.method == 'POST':
        form = ProposalForm(request.POST)
        if form.is_valid():
            proposal = form.save(commit=False)
            proposal.proposed_by = request.user
            # Default voting window: start now, end in 7 days
            if not proposal.voting_start:
                proposal.voting_start = timezone.now()
            if not proposal.voting_end:
                proposal.voting_end = timezone.now() + timedelta(days=7)
            proposal.save()

            log_audit(request, 'create', target_model='Proposal',
                      target_id=proposal.pk, object_repr=proposal.title)

            messages.success(request, f"✅ Proposal “{proposal.title}” created.")
            return redirect('governance:proposal_detail', pk=proposal.pk)
        messages.error(request, "Please fix the errors below.")
    else:
        initial = {
            'voting_start': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'voting_end': (timezone.now() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M'),
        }
        form = ProposalForm(initial=initial)

    return render(request, 'governance/proposal_form.html', {
        'form': form,
        'title': 'New Proposal',
        'button_text': 'Create Proposal',
    })


@login_required
def proposal_edit(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)

    if not (proposal.proposed_by_id == request.user.id
            or request.user.has_perm('governance.change_proposal')):
        messages.error(request, "Permission denied.")
        return redirect('governance:proposal_detail', pk=proposal.pk)

    if proposal.status not in ('draft', 'voting'):
        messages.warning(request, "Only draft or voting proposals can be edited.")
        return redirect('governance:proposal_detail', pk=proposal.pk)

    from .forms import ProposalForm
    if request.method == 'POST':
        form = ProposalForm(request.POST, instance=proposal)
        if form.is_valid():
            form.save()
            log_audit(request, 'update', target_model='Proposal',
                      target_id=proposal.pk, object_repr=proposal.title)
            messages.success(request, "✅ Proposal updated.")
            return redirect('governance:proposal_detail', pk=proposal.pk)
        messages.error(request, "Please fix the errors below.")
    else:
        form = ProposalForm(instance=proposal)

    return render(request, 'governance/proposal_form.html', {
        'form': form,
        'proposal': proposal,
        'title': f'Edit — {proposal.title[:40]}',
        'button_text': 'Save Changes',
    })


@require_POST
@login_required
def proposal_open_voting(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)

    if not (proposal.proposed_by_id == request.user.id
            or request.user.has_perm('governance.change_proposal')):
        messages.error(request, "Permission denied.")
        return redirect('governance:proposal_detail', pk=pk)

    if proposal.status != 'draft':
        messages.warning(request, "Only draft proposals can be opened for voting.")
        return redirect('governance:proposal_detail', pk=pk)

    proposal.status = 'voting'
    proposal.save(update_fields=['status', 'updated_at'])

    log_audit(request, 'proposal_opened', target_model='Proposal',
              target_id=pk, object_repr=proposal.title)

    # ---- Notify every eligible voter ----
    eligible = User.objects.filter(
        office_assignments__is_active=True, is_active=True
    ).exclude(pk=proposal.proposed_by_id).distinct()

    link = reverse('governance:proposal_detail', args=[proposal.pk])
    _notify_many(
        eligible,
        'proposal',
        f"New proposal open for voting: {proposal.title}",
        (
            f"Proposed by {proposal.proposed_by.get_full_name()}\n"
            f"Voting closes: {proposal.voting_end.strftime('%b %d, %Y %H:%M')}\n\n"
            f"{proposal.description[:300]}"
        ),
        link,
    )

    # Email blast
    recipients = list(eligible.exclude(email='').values_list('email', flat=True))
    _send_email(
        subject=f"[NAMETS] New proposal open for voting: {proposal.title}",
        message=(
            f"A new proposal has been opened for voting.\n\n"
            f"Title: {proposal.title}\n"
            f"Proposed by: {proposal.proposed_by.get_full_name()}\n"
            f"Voting closes: {proposal.voting_end.strftime('%b %d, %Y %H:%M')}\n\n"
            f"Cast your vote on the dashboard."
        ),
        recipients=recipients,
        category='voting',
    )

    messages.success(request, f"🗳️ “{proposal.title}” is now open for voting.")
    return redirect('governance:proposal_detail', pk=pk)


@require_POST
@login_required
def proposal_close(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)

    if not _is_wakeel_or_ict(request.user) and not request.user.has_perm('governance.change_proposal'):
        messages.error(request, "Permission denied.")
        return redirect('governance:proposal_detail', pk=pk)

    if proposal.status != 'voting':
        messages.warning(request, "Only voting proposals can be closed.")
        return redirect('governance:proposal_detail', pk=pk)

    result = proposal.decide(by_user=request.user, force=True)

    log_audit(request, 'proposal_closed', target_model='Proposal',
              target_id=pk, object_repr=proposal.title,
              changes={'result': result, 'summary': proposal.result_summary})

    # ---- Notify proposer + all voters ----
    audience = list(proposal.votes.values_list('voter', flat=True))
    if proposal.proposed_by_id:
        audience.append(proposal.proposed_by_id)

    from django.contrib.auth import get_user_model
    users_to_notify = get_user_model().objects.filter(pk__in=set(audience))
    link = reverse('governance:proposal_detail', args=[proposal.pk])
    _notify_many(
        users_to_notify,
        'proposal',
        f"Proposal {proposal.get_status_display().lower()}: {proposal.title}",
        proposal.result_summary or f"Result: {proposal.get_status_display()}",
        link,
    )

    messages.success(request, f"📊 Proposal closed — result: {proposal.get_status_display()}.")
    return redirect('governance:proposal_detail', pk=pk)


@require_POST
@login_required
def proposal_cancel(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)

    if not (proposal.proposed_by_id == request.user.id
            or request.user.has_perm('governance.change_proposal')):
        messages.error(request, "Permission denied.")
        return redirect('governance:proposal_detail', pk=pk)

    if proposal.status in ('passed', 'rejected', 'cancelled'):
        messages.warning(request, "This proposal is already closed.")
        return redirect('governance:proposal_detail', pk=pk)

    # ---- Notify voters BEFORE flipping status ----
    voter_ids = list(proposal.votes.values_list('voter', flat=True)) if proposal.status == 'voting' else []
    if voter_ids:
        from django.contrib.auth import get_user_model
        _notify_many(
            get_user_model().objects.filter(pk__in=voter_ids),
            'proposal',
            f"Proposal cancelled: {proposal.title}",
            f"Cancelled by {request.user.get_full_name() or request.user.email}.",
            reverse('governance:proposal_detail', args=[proposal.pk]),
        )

    proposal.status = 'cancelled'
    proposal.save(update_fields=['status', 'updated_at'])
    log_audit(request, 'proposal_closed', target_model='Proposal',
              target_id=pk, object_repr=proposal.title,
              changes={'result': 'cancelled'})

    messages.success(request, "🚫 Proposal cancelled.")
    return redirect('governance:proposal_detail', pk=pk)


@require_POST
@login_required
def proposal_delete(request, pk):
    if not request.user.has_perm('governance.delete_proposal'):
        messages.error(request, "Permission denied.")
        return redirect('governance:proposal_list')

    proposal = get_object_or_404(Proposal, pk=pk)
    title = proposal.title
    proposal.delete()
    log_audit(request, 'delete', target_model='Proposal',
              target_id=pk, object_repr=title)
    messages.success(request, f"🗑️ Proposal “{title}” deleted.")
    return redirect('governance:proposal_list')


@require_POST
@login_required
def vote_cast(request, pk):
    """Cast or update a vote on a proposal."""
    proposal = get_object_or_404(Proposal, pk=pk)

    if proposal.status != 'voting':
        messages.error(request, "This proposal is not open for voting.")
        return redirect('governance:proposal_detail', pk=pk)

    if not request.user.office_assignments.filter(is_active=True).exists():
        messages.error(request, "Only active EXCO members can vote.")
        return redirect('governance:proposal_detail', pk=pk)

    choice = request.POST.get('choice', '').strip().lower()
    feedback = request.POST.get('feedback', '').strip()

    if choice not in ('agree', 'disagree', 'abstain'):
        messages.error(request, "Please choose Agree, Disagree, or Abstain.")
        return redirect('governance:proposal_detail', pk=pk)

    is_update = False
    existing = proposal.votes.filter(voter=request.user).first()
    if existing:
        existing.choice = choice
        existing.feedback = feedback
        existing.save(update_fields=['choice', 'feedback'])
        is_update = True
        messages.success(request, "✅ Your vote has been updated.")
    else:
        Vote.objects.create(
            proposal=proposal,
            voter=request.user,
            choice=choice,
            feedback=feedback,
        )
        messages.success(request, "✅ Vote recorded. JazakAllah khair.")

    log_audit(request, 'vote_cast', target_model='Proposal',
              target_id=pk, object_repr=proposal.title,
              changes={'choice': choice})

    # ---- Notify the proposer (not themselves) ----
    if proposal.proposed_by_id and proposal.proposed_by_id != request.user.id:
        action_word = "updated their vote on" if is_update else "voted on"
        _notify(
            proposal.proposed_by,
            'vote',
            f"{request.user.get_full_name() or request.user.email} {action_word} “{proposal.title}”",
            f"Choice: {choice.title()}" + (f"\nFeedback: {feedback}" if feedback else ""),
            reverse('governance:proposal_detail', args=[proposal.pk]),
        )

    # If all eligible voters have now voted, auto-decide
    if proposal.total_votes_cast >= proposal.total_eligible_voters:
        proposal.decide(by_user=request.user, force=True)
        messages.info(request, "All eligible members have voted — the proposal has been decided.")

    return redirect('governance:proposal_detail', pk=pk)


# ============================================================
# 5. AUDIT LOG
# ============================================================

@login_required
def audit_list(request):
    if not request.user.has_perm('governance.view_auditlog'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    user = request.user
    can_see_all = _can_view_all_audit(user)
    office = _user_primary_office(user)

    qs = AuditLog.objects.select_related('user', 'office')

    if not can_see_all and office:
        qs = qs.filter(office=office)

    # Filters
    action_filter = request.GET.get('action', '')
    office_filter = request.GET.get('office', '')
    user_filter = request.GET.get('user', '')
    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')
    query = request.GET.get('q', '').strip()

    if action_filter:
        qs = qs.filter(action=action_filter)
    if office_filter and can_see_all:
        qs = qs.filter(office_id=office_filter)
    if user_filter:
        qs = qs.filter(user_id=user_filter)
    if date_from:
        qs = qs.filter(timestamp__date__gte=date_from)
    if date_to:
        qs = qs.filter(timestamp__date__lte=date_to)
    if query:
        qs = qs.filter(
            Q(object_repr__icontains=query)
            | Q(target_model__icontains=query)
            | Q(user__email__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
        )

    qs = qs.order_by('-timestamp')
    page = Paginator(qs, 50).get_page(request.GET.get('page'))

    # Filter choice data
    all_offices = Office.objects.all().order_by('name') if can_see_all else []
    all_users = User.objects.filter(is_active=True).order_by('first_name') if can_see_all else []
    action_choices = AuditLog.ACTION_CHOICES

    return render(request, 'governance/audit_list.html', {
        'logs': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'can_see_all': can_see_all,
        'action_filter': action_filter,
        'office_filter': office_filter,
        'user_filter': user_filter,
        'date_from': date_from,
        'date_to': date_to,
        'query': query,
        'all_offices': all_offices,
        'all_users': all_users,
        'action_choices': action_choices,
    })


@login_required
def audit_detail(request, pk):
    if not request.user.has_perm('governance.view_auditlog'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    log = get_object_or_404(AuditLog.objects.select_related('user', 'office'), pk=pk)

    # Scope check
    if not _can_view_all_audit(request.user):
        office = _user_primary_office(request.user)
        if not office or log.office_id != office.id:
            messages.error(request, "You don't have access to this log entry.")
            return redirect('governance:audit_list')

    return render(request, 'governance/audit_detail.html', {'log': log})


@login_required
def audit_export(request):
    if not request.user.has_perm('governance.view_auditlog'):
        messages.error(request, "Permission denied.")
        return redirect('governance:audit_list')

    user = request.user
    can_see_all = _can_view_all_audit(user)
    office = _user_primary_office(user)

    qs = AuditLog.objects.select_related('user', 'office').order_by('-timestamp')
    if not can_see_all and office:
        qs = qs.filter(office=office)

    # Respect filters
    if request.GET.get('action'):
        qs = qs.filter(action=request.GET['action'])
    if request.GET.get('from'):
        qs = qs.filter(timestamp__date__gte=request.GET['from'])
    if request.GET.get('to'):
        qs = qs.filter(timestamp__date__lte=request.GET['to'])

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Audit Log'

    headers = ['Timestamp', 'Actor', 'Email', 'Action', 'Office',
               'Target Model', 'Object', 'IP Address', 'Details']
    gold = PatternFill(start_color='C9A84C', end_color='C9A84C', fill_type='solid')
    hf = Font(bold=True, color='FFFFFF')
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=i, value=h)
        c.fill = gold
        c.font = hf

    for i, log in enumerate(qs, start=2):
        ws.cell(row=i, column=1, value=log.timestamp.strftime('%Y-%m-%d %H:%M:%S'))
        ws.cell(row=i, column=2, value=log.actor_display)
        ws.cell(row=i, column=3, value=log.user.email if log.user else '')
        ws.cell(row=i, column=4, value=log.get_action_display())
        ws.cell(row=i, column=5, value=log.office.name if log.office else '')
        ws.cell(row=i, column=6, value=log.target_model or '')
        ws.cell(row=i, column=7, value=log.object_repr or '')
        ws.cell(row=i, column=8, value=log.ip_address or '')
        ws.cell(row=i, column=9, value=str(log.changes or ''))

    for i, w in enumerate([20, 25, 25, 20, 20, 20, 40, 15, 50], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"audit_log_{timezone.now():%Y%m%d_%H%M}.xlsx"
    response['Content-Disposition'] = f'attachment; filename={filename}'
    wb.save(response)

    log_audit(request, 'bulk_export', target_model='AuditLog',
              object_repr=f'{qs.count()} entries exported')

    return response


# ============================================================
# 6. NOMINATIONS
# ============================================================

@login_required
def nomination_list(request):
    if not _is_wakeel_or_ict(request.user) and not request.user.has_perm('governance.view_nominationintake'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    qs = NominationIntake.objects.select_related('nominated_office', 'nominated_by').order_by('-created_at')

    status_filter = request.GET.get('status', '')
    session_filter = request.GET.get('session', '')
    query = request.GET.get('q', '').strip()

    if status_filter:
        qs = qs.filter(status=status_filter)
    if session_filter:
        qs = qs.filter(session_label__icontains=session_filter)
    if query:
        qs = qs.filter(
            Q(nominated_name__icontains=query)
            | Q(nominated_email__icontains=query)
            | Q(reason__icontains=query)
        )

    page = Paginator(qs, 30).get_page(request.GET.get('page'))

    return render(request, 'governance/nomination_list.html', {
        'nominations': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'status_filter': status_filter,
        'session_filter': session_filter,
        'query': query,
    })


@login_required
def nomination_create(request):
    if not _is_wakeel_or_ict(request.user) and not request.user.has_perm('governance.add_nominationintake'):
        messages.error(request, "Permission denied.")
        return redirect('governance:nomination_list')

    from .forms import NominationIntakeForm
    if request.method == 'POST':
        form = NominationIntakeForm(request.POST)
        if form.is_valid():
            n = form.save(commit=False)
            n.nominated_by = request.user
            n.save()
            log_audit(request, 'create', target_model='NominationIntake',
                      target_id=n.pk, object_repr=n.nominated_name)

            # ---- Notify Wakeel + ICT Head + superusers ----
            audience = User.objects.filter(
                is_active=True,
            ).filter(
                models.Q(is_superuser=True)
                | models.Q(office_assignments__is_active=True,
                            office_assignments__office__name__icontains='wakeel')
                | models.Q(office_assignments__is_active=True,
                            office_assignments__office__is_protected=True)
            ).distinct()

            _notify_many(
                audience,
                'nomination',
                f"New nomination: {n.nominated_name}",
                (
                    f"Nominated for: {n.nominated_office.name if n.nominated_office else '—'}\n"
                    f"By: {request.user.get_full_name() or request.user.email}\n\n"
                    f"{n.reason[:250]}"
                ),
                reverse('governance:nomination_list'),
            )

            messages.success(request, f"✅ Nomination for “{n.nominated_name}” recorded.")
            return redirect('governance:nomination_list')
        messages.error(request, "Please fix the errors below.")
    else:
        form = NominationIntakeForm()

    return render(request, 'governance/nomination_form.html', {
        'form': form,
        'title': 'New Nomination',
        'button_text': 'Record Nomination',
    })

@login_required
def nomination_edit(request, pk):
    if not _is_wakeel_or_ict(request.user) and not request.user.has_perm('governance.change_nominationintake'):
        messages.error(request, "Permission denied.")
        return redirect('governance:nomination_list')

    n = get_object_or_404(NominationIntake, pk=pk)
    from .forms import NominationIntakeForm

    if request.method == 'POST':
        form = NominationIntakeForm(request.POST, instance=n)
        if form.is_valid():
            form.save()
            log_audit(request, 'update', target_model='NominationIntake',
                      target_id=n.pk, object_repr=n.nominated_name)
            messages.success(request, "✅ Nomination updated.")
            return redirect('governance:nomination_list')
        messages.error(request, "Please fix the errors below.")
    else:
        form = NominationIntakeForm(instance=n)

    return render(request, 'governance/nomination_form.html', {
        'form': form,
        'nomination': n,
        'title': f'Edit — {n.nominated_name}',
        'button_text': 'Save Changes',
    })


@require_POST
@login_required
def nomination_set_status(request, pk):
    if not _is_wakeel_or_ict(request.user) and not request.user.has_perm('governance.change_nominationintake'):
        messages.error(request, "Permission denied.")
        return redirect('governance:nomination_list')

    n = get_object_or_404(NominationIntake, pk=pk)
    status = request.POST.get('status', '')
    if status not in dict(NominationIntake.STATUS_CHOICES):
        messages.error(request, "Invalid status.")
        return redirect('governance:nomination_list')

    n.status = status
    n.save(update_fields=['status'])
    log_audit(request, 'update', target_model='NominationIntake',
              target_id=n.pk, object_repr=n.nominated_name,
              changes={'status': status})
    messages.success(request, f"✅ Status set to {n.get_status_display()}.")
    return redirect('governance:nomination_list')


@require_POST
@login_required
def nomination_delete(request, pk):
    if not request.user.has_perm('governance.delete_nominationintake'):
        messages.error(request, "Permission denied.")
        return redirect('governance:nomination_list')

    n = get_object_or_404(NominationIntake, pk=pk)
    name = n.nominated_name
    n.delete()
    log_audit(request, 'delete', target_model='NominationIntake',
              target_id=pk, object_repr=name)
    messages.success(request, f"🗑️ Nomination for “{name}” deleted.")
    return redirect('governance:nomination_list')


# ============================================================
# 7. SELECTION RECORDS
# ============================================================

@login_required
def selection_list(request):
    if not _is_wakeel_or_ict(request.user) and not request.user.has_perm('governance.view_selectionrecord'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    qs = SelectionRecord.objects.select_related('finalized_by').order_by('-finalized_at')
    page = Paginator(qs, 20).get_page(request.GET.get('page'))

    return render(request, 'governance/selection_list.html', {
        'records': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
    })


@login_required
def selection_detail(request, pk):
    if not _is_wakeel_or_ict(request.user) and not request.user.has_perm('governance.view_selectionrecord'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    record = get_object_or_404(SelectionRecord, pk=pk)
    return render(request, 'governance/selection_detail.html', {'record': record})


@login_required
def selection_create(request):
    if not _is_wakeel_or_ict(request.user) and not request.user.has_perm('governance.add_selectionrecord'):
        messages.error(request, "Permission denied.")
        return redirect('governance:selection_list')

    from .forms import SelectionRecordForm
    if request.method == 'POST':
        form = SelectionRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.finalized_by = request.user
            record.save()
            log_audit(request, 'create', target_model='SelectionRecord',
                      target_id=record.pk, object_repr=record.session_label)
            messages.success(request, f"✅ Selection record for {record.session_label} created.")
            return redirect('governance:selection_detail', pk=record.pk)
        messages.error(request, "Please fix the errors below.")
    else:
        form = SelectionRecordForm()

    return render(request, 'governance/selection_form.html', {
        'form': form,
        'title': 'New Selection Record',
        'button_text': 'Create Record',
    })


@require_POST
@login_required
def selection_publish(request, pk):
    if not _is_wakeel_or_ict(request.user) and not request.user.has_perm('governance.change_selectionrecord'):
        messages.error(request, "Permission denied.")
        return redirect('governance:selection_list')

    record = get_object_or_404(SelectionRecord, pk=pk)
    record.is_published = not record.is_published
    record.save(update_fields=['is_published'])
    log_audit(request, 'update', target_model='SelectionRecord',
              target_id=record.pk, object_repr=record.session_label,
              changes={'is_published': record.is_published})

    state = 'published' if record.is_published else 'unpublished'

    # ---- Only notify on PUBLISH, not unpublish ----
    if record.is_published:
        audience = User.objects.filter(
            is_active=True,
            office_assignments__is_active=True,
        ).distinct()
        _notify_many(
            audience,
            'governance',
            f"Selection record published — {record.session_label}",
            "The final selection for this session is now available to view.",
            reverse('governance:selection_detail', args=[record.pk]),
        )

    messages.success(request, f"✅ Selection record {state}.")
    return redirect('governance:selection_detail', pk=pk)


@require_POST
@login_required
def selection_delete(request, pk):
    if not request.user.has_perm('governance.delete_selectionrecord'):
        messages.error(request, "Permission denied.")
        return redirect('governance:selection_list')

    record = get_object_or_404(SelectionRecord, pk=pk)
    label = record.session_label
    record.delete()
    log_audit(request, 'delete', target_model='SelectionRecord',
              target_id=pk, object_repr=label)
    messages.success(request, f"🗑️ Selection record “{label}” deleted.")
    return redirect('governance:selection_list')


# ============================================================
# 8. OATH ACKNOWLEDGMENTS
# ============================================================

@login_required
def oath_list(request):
    if not _is_wakeel_or_ict(request.user) and not request.user.has_perm('governance.view_oathacknowledgment'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    qs = OathAcknowledgment.objects.select_related('user').order_by('-acknowledged_at')
    page = Paginator(qs, 40).get_page(request.GET.get('page'))

    all_users = User.objects.filter(
        is_active=True,
        office_assignments__is_active=True,
    ).distinct().order_by('first_name', 'last_name')

    return render(request, 'governance/oath_list.html', {
        'acknowledgments': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'all_users': all_users,
    })


@require_POST
@login_required
def oath_record(request):
    """Mark a user as having taken the oath for a given session."""
    if not _is_wakeel_or_ict(request.user) and not request.user.has_perm('governance.add_oathacknowledgment'):
        messages.error(request, "Permission denied.")
        return redirect('governance:oath_list')

    user_id = request.POST.get('user')
    session_label = request.POST.get('session_label', '').strip()
    notes = request.POST.get('notes', '').strip()

    if not user_id or not session_label:
        messages.error(request, "User and session label are required.")
        return redirect('governance:oath_list')

    target_user = get_object_or_404(User, pk=user_id)
    obj, created = OathAcknowledgment.objects.get_or_create(
        user=target_user,
        session_label=session_label,
        defaults={'notes': notes},
    )
    if not created:
        messages.info(request, f"{target_user.get_full_name()} already has an oath for {session_label}.")
    else:
        log_audit(request, 'create', target_model='OathAcknowledgment',
                  target_id=obj.pk, object_repr=f"{target_user.get_full_name()} → {session_label}")

        # ---- Notify the newly-oath-bound member ----
        _notify(
            target_user,
            'oath',
            f"Oath recorded — {session_label}",
            (
                f"Assalamu Alaikum {target_user.get_full_name()},\n\n"
                f"Your oath of allegiance for the {session_label} session has been recorded. "
                f"Baarakallahu feek."
            ),
            reverse('governance:oath_list'),
        )

        messages.success(request, f"✅ Oath recorded for {target_user.get_full_name()}.")

    return redirect('governance:oath_list')

# ============================================================
# 9. HANDOVER
# ============================================================

@login_required
def handover_confirm(request):
    """Show a confirmation page listing what will be dissolved."""
    if not _is_wakeel_or_ict(request.user):
        messages.error(request, "Only the Wakeel or ICT Head can initiate handover.")
        return redirect('governance:dashboard')

    active_assignments = OfficeAssignment.objects.filter(
        is_active=True
    ).select_related('user', 'office')

    to_dissolve = []
    to_skip = []
    for a in active_assignments:
        if a.office.is_protected:
            to_skip.append(a)
        else:
            to_dissolve.append(a)

    return render(request, 'governance/handover_confirm.html', {
        'to_dissolve': to_dissolve,
        'to_skip': to_skip,
        'total_active': active_assignments.count(),
    })


@require_POST
@login_required
def handover_execute(request):
    """Actually dissolve the EXCO — the big dangerous action."""
    if not _is_wakeel_or_ict(request.user):
        messages.error(request, "Only the Wakeel or ICT Head can execute handover.")
        return redirect('governance:dashboard')

    if request.POST.get('confirmed') != 'yes':
        messages.error(request, "Handover was not confirmed.")
        return redirect('governance:handover_confirm')

    session_ending = request.POST.get('session_ending', '').strip()
    session_starting = request.POST.get('session_starting', '').strip()
    notes = request.POST.get('notes', '').strip()

    active_assignments = OfficeAssignment.objects.filter(
        is_active=True
    ).select_related('user', 'office')

    dissolved_count = 0
    protected_skipped = 0
    year = timezone.now().year
    dissolved_users = []

    for a in active_assignments:
        if a.office.is_protected:
            protected_skipped += 1
            continue

        a.is_active = False
        a.save(update_fields=['is_active'])

        a.user.is_alumni = True
        a.user.save(update_fields=['is_alumni'])

        if not hasattr(a.user, 'graduation_profile'):
            offices_held = []
            for past in a.user.office_assignments.select_related('office'):
                offices_held.append({
                    'office': past.office.name,
                    'display_label': past.display_label or '',
                    'is_active': past.is_active,
                })
            GraduationProfile.objects.create(
                user=a.user,
                graduation_year=year,
                department_name=a.user.department.name if a.user.department else '',
                phone_number=a.user.phone_number or '',
                email=a.user.email or '',
                offices_held=offices_held,
                tasks_completed=Task.objects.filter(assigned_to=a.user, status='completed').count(),
                proposals_passed=Proposal.objects.filter(proposed_by=a.user, status='passed').count(),
            )

        dissolved_users.append(a.user)

        # ---- In-app notification ----
        _notify(
            a.user,
            'handover',
            "Your EXCO term has ended — welcome to the Alumni!",
            (
                f"Assalamu Alaikum {a.user.get_full_name()},\n\n"
                f"Your time on the NAMETS EXCO has come to an end. "
                f"Thank you for your service — may Allah reward you abundantly.\n\n"
                f"A Graduation Profile has been created for you. You can now edit it "
                f"from the Alumni section."
            ),
            reverse('governance:graduation_list'),
        )

        # ---- Email (existing behaviour) ----
        _send_email(
            subject="Thank you for your service — you're now a NAMETS Alumnus",
            message=(
                f"Assalamu Alaikum {a.user.get_full_name()},\n\n"
                f"Your time on the NAMETS EXCO has come to an end. "
                f"Thank you for your service — may Allah reward you abundantly.\n\n"
                f"You are now marked as an Alumnus. Your graduation profile "
                f"has been recorded and can be seen by other alumni and current EXCO."
            ),
            recipients=[a.user.email],
            category='general',
        )
        dissolved_count += 1

    log = HandoverLog.objects.create(
        initiated_by=request.user,
        session_ending=session_ending,
        session_starting=session_starting,
        dissolved_count=dissolved_count,
        protected_skipped=protected_skipped,
        notes=notes,
    )

    log_audit(request, 'handover', target_model='HandoverLog',
              target_id=log.pk, object_repr='EXCO dissolved',
              changes={'dissolved': dissolved_count,
                       'protected_skipped': protected_skipped,
                       'session_ending': session_ending,
                       'session_starting': session_starting})

    messages.success(
        request,
        f"✅ Handover complete. {dissolved_count} assignment(s) dissolved, "
        f"{protected_skipped} protected office(s) preserved."
    )
    return redirect('governance:dashboard')


@login_required
def handover_history(request):
    if not _is_wakeel_or_ict(request.user):
        messages.error(request, "Permission denied.")
        return redirect('governance:dashboard')

    qs = HandoverLog.objects.select_related('initiated_by').order_by('-timestamp')
    page = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'governance/handover_history.html', {
        'logs': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
    })


# ============================================================
# 10. GRADUATION PROFILES
# ============================================================

@login_required
def graduation_list(request):
    if not request.user.has_perm('governance.view_graduationprofile'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    qs = GraduationProfile.objects.select_related('user').order_by('-graduation_year', 'user__first_name')
    year_filter = request.GET.get('year', '')
    query = request.GET.get('q', '').strip()

    if year_filter:
        qs = qs.filter(graduation_year=year_filter)
    if query:
        qs = qs.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(department_name__icontains=query)
        )

    page = Paginator(qs, 30).get_page(request.GET.get('page'))
    years = GraduationProfile.objects.values_list('graduation_year', flat=True).distinct().order_by('-graduation_year')

    return render(request, 'governance/graduation_list.html', {
        'profiles': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'year_filter': year_filter,
        'query': query,
        'years': years,
    })


@login_required
def graduation_detail(request, pk):
    profile = get_object_or_404(GraduationProfile.objects.select_related('user'), pk=pk)

    # Anyone who is alumni or current EXCO can view
    is_visible = (
        request.user.is_alumni
        or request.user.office_assignments.filter(is_active=True).exists()
        or _is_wakeel_or_ict(request.user)
    )
    if not is_visible:
        messages.error(request, "You don't have access to this profile.")
        return redirect('dashboards:dashboard')

    return render(request, 'governance/graduation_detail.html', {'profile': profile})


# ============================================================
# 11. DELEGATION
# ============================================================

@login_required
def delegation_home(request):
    """
    Office head grants/revokes permissions to members of THEIR OWN office,
    but only the permissions their own office already holds.
    """
    from django.contrib.auth.models import Permission

    office = _user_primary_office(request.user)
    if not office:
        messages.error(request, "You don't hold an active office.")
        return redirect('dashboards:dashboard')

    # Get the permissions this office holds
    office_permissions = office.permissions.all()
    if not office_permissions.exists():
        messages.info(request, "Your office doesn't have any permissions configured yet.")
        return redirect('governance:dashboard')

    # Everyone else in the same office (excluding me)
    colleagues = OfficeAssignment.objects.filter(
        office=office, is_active=True
    ).exclude(user=request.user).select_related('user')

    colleagues_data = []
    for c in colleagues:
        u = c.user
        current = set(u.user_permissions.values_list('id', flat=True))
        # Which of my office's permissions does this colleague already have?
        granted_ids = {p.id for p in office_permissions if p.id in current}
        colleagues_data.append({
            'assignment': c,
            'user': u,
            'granted_ids': granted_ids,
        })

    if request.method == 'POST':
        target_user_id = request.POST.get('user_id')
        target_user = get_object_or_404(User, pk=target_user_id)

        # Confirm target is a member of the same office
        is_member = OfficeAssignment.objects.filter(
            office=office, user=target_user, is_active=True
        ).exists()
        if not is_member:
            messages.error(request, "That user is not a member of your office.")
            return redirect('governance:delegation_home')

        submitted_ids = set(int(pid) for pid in request.POST.getlist('permissions') if pid.isdigit())
        allowed_ids = set(office_permissions.values_list('id', flat=True))

        # Only permissions the office already has
        to_grant = submitted_ids & allowed_ids

        # Current user permissions
        current_user_perms = set(target_user.user_permissions.values_list('id', flat=True))

        # We only touch permissions that are in the office's scope
        outside_scope = current_user_perms - allowed_ids
        new_perms = outside_scope | to_grant

        # Diff for the audit log
        granted = to_grant - current_user_perms
        revoked = (current_user_perms & allowed_ids) - to_grant

        target_user.user_permissions.set(Permission.objects.filter(id__in=new_perms))

        if granted:
            log_audit(request, 'permission_granted',
                      office=office,
                      target_model='User',
                      target_id=target_user.id,
                      object_repr=target_user.get_full_name(),
                      changes={'granted_ids': list(granted),
                               'permission_names': list(
                                   Permission.objects.filter(id__in=granted).values_list('name', flat=True)
                               )})
        if revoked:
            log_audit(request, 'permission_revoked',
                      office=office,
                      target_model='User',
                      target_id=target_user.id,
                      object_repr=target_user.get_full_name(),
                      changes={'revoked_ids': list(revoked),
                               'permission_names': list(
                                   Permission.objects.filter(id__in=revoked).values_list('name', flat=True)
                               )})

        messages.success(
            request,
            f"✅ Permissions updated for {target_user.get_full_name()} "
            f"({len(granted)} granted, {len(revoked)} revoked)."
        )
        return redirect('governance:delegation_home')

    # Group permissions by app for the UI
    grouped = {}
    for p in office_permissions.select_related('content_type'):
        app_label = p.content_type.app_label
        grouped.setdefault(app_label, []).append(p)

    return render(request, 'governance/delegation_home.html', {
        'office': office,
        'colleagues_data': colleagues_data,
        'grouped_permissions': grouped,
        'office_permission_count': office_permissions.count(),
    })
    
    
    
# ============================================================
# 12. OFFICE & PERMISSION MANAGEMENT
# ============================================================

def _can_manage_offices(user):
    """Wakeel, ICT Head, or superuser only."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if user.office_assignments.filter(
        is_active=True, office__is_protected=True
    ).exists():
        return True
    return user.office_assignments.filter(
        is_active=True, office__name__icontains='wakeel'
    ).exists()


@login_required
def office_list(request):
    if not _can_manage_offices(request.user):
        messages.error(request, "Only the Wakeel or ICT Head can manage offices.")
        return redirect('governance:dashboard')

    offices = Office.objects.annotate(
        perm_count=Count('permissions', distinct=True),
        member_count=Count(
            'officeassignment',
            filter=Q(officeassignment__is_active=True),
            distinct=True,
        ),
    ).order_by('name')
    
    page = Paginator(offices, 30).get_page(request.GET.get('page'))

    return render(request, 'governance/office_list.html', {
        'offices': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
    })


@login_required
def office_create(request):
    if not _can_manage_offices(request.user):
        messages.error(request, "Permission denied.")
        return redirect('governance:office_list')

    from .forms import OfficeForm
    if request.method == 'POST':
        form = OfficeForm(request.POST)
        if form.is_valid():
            office = form.save()
            log_audit(request, 'create', target_model='Office',
                      target_id=office.pk, object_repr=office.name)
            messages.success(request, f"✅ Office “{office.name}” created. Now assign its permissions.")
            return redirect('governance:office_permissions', pk=office.pk)
        messages.error(request, "Please fix the errors below.")
    else:
        form = OfficeForm()

    return render(request, 'governance/office_form.html', {
        'form': form,
        'title': 'Create Office',
        'button_text': 'Create Office',
    })


@login_required
def office_edit(request, pk):
    if not _can_manage_offices(request.user):
        messages.error(request, "Permission denied.")
        return redirect('governance:office_list')

    office = get_object_or_404(Office, pk=pk)
    from .forms import OfficeForm

    if request.method == 'POST':
        form = OfficeForm(request.POST, instance=office)
        if form.is_valid():
            form.save()
            log_audit(request, 'update', target_model='Office',
                      target_id=office.pk, object_repr=office.name)
            messages.success(request, f"✅ Office “{office.name}” updated.")
            return redirect('governance:office_list')
        messages.error(request, "Please fix the errors below.")
    else:
        form = OfficeForm(instance=office)

    return render(request, 'governance/office_form.html', {
        'form': form,
        'office': office,
        'title': f'Edit — {office.name}',
        'button_text': 'Save Changes',
    })


@require_POST
@login_required
def office_delete(request, pk):
    if not _can_manage_offices(request.user):
        messages.error(request, "Permission denied.")
        return redirect('governance:office_list')

    office = get_object_or_404(Office, pk=pk)

    if office.is_protected:
        messages.error(request, "Protected offices (like ICT Head) cannot be deleted.")
        return redirect('governance:office_list')

    name = office.name
    office.delete()
    log_audit(request, 'delete', target_model='Office',
              target_id=pk, object_repr=name)
    messages.success(request, f"🗑️ Office “{name}” deleted.")
    return redirect('governance:office_list')


@login_required
def office_permissions(request, pk):
    if not _can_manage_offices(request.user):
        messages.error(request, "Permission denied.")
        return redirect('governance:office_list')

    from django.contrib.auth.models import Permission

    office = get_object_or_404(Office, pk=pk)

    if request.method == 'POST':
        submitted_ids = set(
            int(pid) for pid in request.POST.getlist('permissions') if pid.isdigit()
        )
        current_ids = set(office.permissions.values_list('id', flat=True))

        to_add = submitted_ids - current_ids
        to_remove = current_ids - submitted_ids

        office.permissions.set(Permission.objects.filter(id__in=submitted_ids))

        if to_add or to_remove:
            log_audit(
                request,
                'permission_granted' if to_add else 'permission_revoked',
                target_model='Office',
                target_id=office.pk,
                object_repr=office.name,
                changes={
                    'added_count': len(to_add),
                    'removed_count': len(to_remove),
                    'total_after': len(submitted_ids),
                },
            )

        messages.success(
            request,
            f"✅ Permissions updated for “{office.name}” — "
            f"{len(to_add)} added, {len(to_remove)} removed."
        )
        return redirect('governance:office_permissions', pk=office.pk)

    all_perms = Permission.objects.select_related('content_type').order_by(
        'content_type__app_label', 'codename'
    )
    current_ids = set(office.permissions.values_list('id', flat=True))

    grouped = {}
    for p in all_perms:
        app_label = p.content_type.app_label
        grouped.setdefault(app_label, []).append({
            'perm': p,
            'granted': p.id in current_ids,
        })

    # Recent permission-change history for this office
    recent_changes = AuditLog.objects.filter(
        target_model='Office',
        target_id=office.pk,
        action__in=['permission_granted', 'permission_revoked'],
    ).select_related('user').order_by('-timestamp')[:5]

    return render(request, 'governance/office_permissions.html', {
        'office': office,
        'grouped_permissions': grouped,
        'total_perms': all_perms.count(),
        'current_count': len(current_ids),
        'recent_changes': recent_changes,
    })


@login_required
def user_office_assignment(request, user_id=None):
    if not _can_manage_offices(request.user):
        messages.error(request, "Permission denied.")
        return redirect('governance:office_list')

    target_user = None
    if user_id:
        target_user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        user_pk = request.POST.get('user')
        office_pk = request.POST.get('office')
        display_label = request.POST.get('display_label', '').strip()

        if not user_pk or not office_pk:
            messages.error(request, "Please select both a user and an office.")
        else:
            target_u = get_object_or_404(User, pk=user_pk)
            target_o = get_object_or_404(Office, pk=office_pk)

            existing = OfficeAssignment.objects.filter(
                user=target_u, office=target_o, is_active=True
            ).first()

            if existing:
                existing.display_label = display_label
                existing.save(update_fields=['display_label'])
                messages.info(
                    request,
                    f"{target_u.get_full_name() or target_u.username} already holds "
                    f"this office — display label updated."
                )
            else:
                OfficeAssignment.objects.create(
                    user=target_u,
                    office=target_o,
                    display_label=display_label,
                    is_active=True,
                )
                log_audit(
                    request, 'update', target_model='OfficeAssignment',
                    target_id=target_u.pk,
                    object_repr=f"{target_u.get_full_name() or target_u.username} → {target_o.name}",
                    changes={'display_label': display_label},
                )

                # ---- Notify the assigned user ----
                _notify(
                    target_u,
                    'governance',
                    f"You've been assigned to {target_o.name}",
                    (
                        f"Assalamu Alaikum {target_u.get_full_name() or target_u.username},\n\n"
                        f"You are now a member of the {target_o.name} office"
                        + (f" ({display_label})" if display_label else "")
                        + ". Your new permissions are now active."
                    ),
                    reverse('dashboards:dashboard'),
                )

                messages.success(
                    request,
                    f"✅ {target_u.get_full_name() or target_u.username} assigned to {target_o.name}."
                )

        return redirect('governance:user_office_assignment')

    assignments = (
        OfficeAssignment.objects
        .filter(is_active=True)
        .select_related('user', 'office')
        .order_by('office__name', 'user__first_name')
    )

    active_users = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
    all_offices = Office.objects.all().order_by('name')

    return render(request, 'governance/user_office_assignment.html', {
        'assignments': assignments,
        'active_users': active_users,
        'all_offices': all_offices,
        'target_user': target_user,
    })


@require_POST
@login_required
def user_office_unassign(request, pk):
    if not _can_manage_offices(request.user):
        messages.error(request, "Permission denied.")
        return redirect('governance:office_list')

    assignment = get_object_or_404(OfficeAssignment, pk=pk)

    if assignment.office.is_protected:
        messages.error(request, "Protected office assignments cannot be removed this way.")
        return redirect('governance:user_office_assignment')

    name = assignment.user.get_full_name() or assignment.user.username
    office_name = assignment.office.name
    affected_user = assignment.user

    assignment.is_active = False
    assignment.save(update_fields=['is_active'])

    log_audit(
        request, 'update', target_model='OfficeAssignment',
        object_repr=f"{name} → {office_name}",
        changes={'is_active': False},
    )

    # ---- Notify the affected user ----
    _notify(
        affected_user,
        'governance',
        f"You've been removed from {office_name}",
        (
            f"Your assignment to the {office_name} office has ended. "
            f"If you believe this is an error, contact the ICT Head."
        ),
        reverse('dashboards:dashboard'),
    )

    messages.success(request, f"✅ {name} removed from {office_name}.")
    return redirect('governance:user_office_assignment')    
    
# ============================================================
# 13. USER MANAGEMENT (super admin scope)
# ============================================================

from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

AuthUser = get_user_model()


def _can_manage_users(user):
    """True if this user can manage ALL users (super admin level)."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return (
        user.has_perm('auth.change_user')
        or user.has_perm('accounts.change_user')
        or user.has_perm('governance.change_user')
    )


def _can_manage_groups(user):
    """True if this user can manage permission groups."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.has_perm('auth.change_group') or user.has_perm('governance.change_group')


@login_required
def user_list(request):
    """Full user management — only for super-admins."""
    if not _can_manage_users(request.user):
        messages.error(request, "Only a super admin can manage all users.")
        return redirect('governance:dashboard')

    qs = AuthUser.objects.all().order_by('-is_active', 'first_name', 'last_name')

    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    role = request.GET.get('role', '')

    if q:
        qs = qs.filter(
            Q(email__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(username__icontains=q)
        )

    if status == 'active':
        qs = qs.filter(is_active=True)
    elif status == 'inactive':
        qs = qs.filter(is_active=False)
    elif status == 'staff':
        qs = qs.filter(is_staff=True)
    elif status == 'superuser':
        qs = qs.filter(is_superuser=True)
    elif status == 'alumni':
        qs = qs.filter(is_alumni=True)

    if role == 'exco':
        qs = qs.filter(office_assignments__is_active=True).distinct()
    elif role == 'no_office':
        qs = qs.exclude(office_assignments__is_active=True)

    page = Paginator(qs, 40).get_page(request.GET.get('page'))

    return render(request, 'governance/user_list.html', {
        'users': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'q': q,
        'status': status,
        'role': role,
        'total_users': AuthUser.objects.count(),
        'active_users': AuthUser.objects.filter(is_active=True).count(),
        'staff_users': AuthUser.objects.filter(is_staff=True).count(),
    })


@login_required
def user_edit(request, pk):
    """Edit any user — info, active status, groups, and direct permissions."""
    if not _can_manage_users(request.user):
        messages.error(request, "Permission denied.")
        return redirect('governance:dashboard')

    target = get_object_or_404(AuthUser, pk=pk)

    # Cannot edit a superuser unless you are one
    if target.is_superuser and not request.user.is_superuser:
        messages.error(request, "Only a superuser can edit a superuser.")
        return redirect('governance:user_list')

    if request.method == 'POST':
        action = request.POST.get('action', 'save_info')

        if action == 'save_info':
            target.first_name = request.POST.get('first_name', '').strip()
            target.last_name = request.POST.get('last_name', '').strip()
            target.email = request.POST.get('email', '').strip()
            target.phone_number = request.POST.get('phone_number', '').strip()
            target.matric_number = request.POST.get('matric_number', '').strip()

            # is_active / is_staff / is_superuser only toggleable by superuser
            if request.user.is_superuser:
                target.is_active = 'is_active' in request.POST
                target.is_staff = 'is_staff' in request.POST
                # Never allow untoggling self
                if target.pk == request.user.pk:
                    target.is_active = True

            target.save()
            log_audit(request, 'update', target_model='User',
                      target_id=target.pk, object_repr=target.email)
            messages.success(request, f"✅ Info saved for {target.get_full_name() or target.email}.")

        elif action == 'save_password':
            if not request.user.is_superuser:
                messages.error(request, "Only a superuser can change passwords.")
            else:
                new_password = request.POST.get('new_password', '').strip()
                if len(new_password) < 8:
                    messages.error(request, "Password must be at least 8 characters.")
                else:
                    target.password = make_password(new_password)
                    target.must_change_password = True
                    target.save(update_fields=['password', 'must_change_password'])
                    log_audit(request, 'update', target_model='User',
                              target_id=target.pk, object_repr=f"Password reset for {target.email}")
                    messages.success(request, "✅ Password changed. User will be forced to reset it on next login.")

        elif action == 'save_groups':
            group_ids = request.POST.getlist('groups')
            target.groups.set(Group.objects.filter(id__in=group_ids))
            log_audit(request, 'update', target_model='User',
                      target_id=target.pk, object_repr=target.email,
                      changes={'groups': group_ids})
            messages.success(request, "✅ Groups updated.")

        elif action == 'save_permissions':
            perm_ids = request.POST.getlist('permissions')
            target.user_permissions.set(Permission.objects.filter(id__in=perm_ids))
            log_audit(request, 'permission_granted', target_model='User',
                      target_id=target.pk, object_repr=target.email,
                      changes={'permission_count': len(perm_ids)})
            messages.success(request, "✅ Direct permissions updated.")

        return redirect('governance:user_edit', pk=target.pk)

    # Fetch data for rendering
    all_groups = Group.objects.all().order_by('name')
    user_group_ids = set(target.groups.values_list('id', flat=True))

    all_perms = Permission.objects.select_related('content_type').order_by(
        'content_type__app_label', 'codename'
    )
    user_perm_ids = set(target.user_permissions.values_list('id', flat=True))

    # Group permissions by app
    grouped_perms = {}
    for p in all_perms:
        app_label = p.content_type.app_label
        grouped_perms.setdefault(app_label, []).append({
            'perm': p,
            'granted': p.id in user_perm_ids,
        })

    # What permissions does this user actually have right now (direct + via groups)?
    effective_perm_ids = set(
        target.get_all_permissions()
    ) if hasattr(target, 'get_all_permissions') else set()

    return render(request, 'governance/user_edit.html', {
        'target': target,
        'all_groups': all_groups,
        'user_group_ids': user_group_ids,
        'grouped_permissions': grouped_perms,
        'total_perms': all_perms.count(),
        'direct_perm_count': len(user_perm_ids),
        'office_assignments': target.office_assignments.select_related('office').order_by('-is_active', 'office__name'),
    })


@require_POST
@login_required
def user_delete(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Only a superuser can delete users.")
        return redirect('governance:user_list')

    target = get_object_or_404(AuthUser, pk=pk)

    if target.pk == request.user.pk:
        messages.error(request, "You cannot delete yourself.")
        return redirect('governance:user_list')

    if target.is_superuser:
        messages.error(request, "Cannot delete another superuser.")
        return redirect('governance:user_list')

    name = target.get_full_name() or target.email
    target.delete()
    log_audit(request, 'delete', target_model='User',
              target_id=pk, object_repr=name)
    messages.success(request, f"🗑️ User “{name}” deleted.")
    return redirect('governance:user_list')


# ============================================================
# 14. GROUP MANAGEMENT
# ============================================================

@login_required
def group_list(request):
    if not _can_manage_groups(request.user):
        messages.error(request, "Permission denied.")
        return redirect('governance:dashboard')

    groups = Group.objects.annotate(
        perm_count=Count('permissions', distinct=True),
        user_count=Count('user', distinct=True),
    ).order_by('name')

    page = Paginator(groups, 30).get_page(request.GET.get('page'))

    return render(request, 'governance/group_list.html', {
        'groups': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'total_groups': Group.objects.count(),
    })


@login_required
def group_form(request, pk=None):
    if not _can_manage_groups(request.user):
        messages.error(request, "Permission denied.")
        return redirect('governance:dashboard')

    group = get_object_or_404(Group, pk=pk) if pk else None

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, "Group name is required.")
        else:
            # Check for duplicates
            existing = Group.objects.filter(name__iexact=name).exclude(pk=pk).first()
            if existing:
                messages.error(request, f"A group named “{name}” already exists.")
            else:
                if group:
                    old_name = group.name
                    group.name = name
                    group.save()
                    log_audit(request, 'update', target_model='Group',
                              target_id=group.pk, object_repr=name,
                              changes={'old_name': old_name})
                    messages.success(request, f"✅ Group renamed to “{name}”.")
                else:
                    group = Group.objects.create(name=name)
                    log_audit(request, 'create', target_model='Group',
                              target_id=group.pk, object_repr=name)
                    messages.success(request, f"✅ Group “{name}” created. Now pick its permissions.")
                    return redirect('governance:group_permissions', pk=group.pk)
                return redirect('governance:group_list')

    return render(request, 'governance/group_form.html', {
        'group': group,
        'title': f'Edit Group — {group.name}' if group else 'Create Group',
        'button_text': 'Save Changes' if group else 'Create Group',
    })


@require_POST
@login_required
def group_delete(request, pk):
    if not _can_manage_groups(request.user):
        messages.error(request, "Permission denied.")
        return redirect('governance:group_list')

    group = get_object_or_404(Group, pk=pk)

    # Protect the default groups created by Django
    protected = {'admin', 'editor', 'viewer'}
    if group.name.lower() in protected and not request.user.is_superuser:
        messages.error(request, f"Group “{group.name}” is protected.")
        return redirect('governance:group_list')

    name = group.name
    group.delete()
    log_audit(request, 'delete', target_model='Group',
              target_id=pk, object_repr=name)
    messages.success(request, f"🗑️ Group “{name}” deleted.")
    return redirect('governance:group_list')


@login_required
def group_permissions(request, pk):
    """Assign permissions to a group."""
    if not _can_manage_groups(request.user):
        messages.error(request, "Permission denied.")
        return redirect('governance:dashboard')

    group = get_object_or_404(Group, pk=pk)

    if request.method == 'POST':
        submitted_ids = set(
            int(pid) for pid in request.POST.getlist('permissions') if pid.isdigit()
        )
        current_ids = set(group.permissions.values_list('id', flat=True))

        to_add = submitted_ids - current_ids
        to_remove = current_ids - submitted_ids

        group.permissions.set(Permission.objects.filter(id__in=submitted_ids))

        if to_add or to_remove:
            log_audit(
                request,
                'permission_granted' if to_add else 'permission_revoked',
                target_model='Group',
                target_id=group.pk,
                object_repr=group.name,
                changes={
                    'added_count': len(to_add),
                    'removed_count': len(to_remove),
                    'total_after': len(submitted_ids),
                },
            )

        messages.success(
            request,
            f"✅ Permissions updated — {len(to_add)} added, {len(to_remove)} removed."
        )
        return redirect('governance:group_permissions', pk=group.pk)

    all_perms = Permission.objects.select_related('content_type').order_by(
        'content_type__app_label', 'codename'
    )
    current_ids = set(group.permissions.values_list('id', flat=True))

    grouped = {}
    for p in all_perms:
        app_label = p.content_type.app_label
        grouped.setdefault(app_label, []).append({
            'perm': p,
            'granted': p.id in current_ids,
        })

    # Members of this group
    members = group.user_set.all().order_by('first_name', 'last_name')

    return render(request, 'governance/group_permissions.html', {
        'group': group,
        'grouped_permissions': grouped,
        'total_perms': all_perms.count(),
        'current_count': len(current_ids),
        'members': members,
    })


# ============================================================
# 15. ENHANCED DELEGATION
# ============================================================

@login_required
def delegation_home(request):
    """
    Delegation page.

    - Super admins see ALL users with full control (link to full editor).
    - Office heads see only their own office's members with office-scoped perms.
    """
    office = _user_primary_office(request.user)
    can_manage_all = _can_manage_users(request.user)

    # ---------- SUPER ADMIN MODE ----------
    if can_manage_all:
        # Show ALL active users, grouped by office + unassigned
        all_users = AuthUser.objects.filter(is_active=True).order_by(
            'first_name', 'last_name'
        )

        # Users with active offices
        office_members = {}
        for a in OfficeAssignment.objects.filter(
            is_active=True
        ).select_related('user', 'office').order_by('office__name', 'user__first_name'):
            office_members.setdefault(a.office, []).append(a)

        unassigned = [
            u for u in all_users
            if not u.office_assignments.filter(is_active=True).exists()
        ]

        return render(request, 'governance/delegation_super.html', {
            'office': office,
            'can_manage_all': True,
            'office_members': office_members.items(),
            'unassigned_users': unassigned,
            'total_users': all_users.count(),
            'total_groups': Group.objects.count(),
        })

    # ---------- OFFICE HEAD MODE ----------
    if not office:
        messages.error(request, "You don't hold an active office.")
        return redirect('governance:dashboard')

    office_permissions = office.permissions.all()
    if not office_permissions.exists():
        messages.info(request, "Your office doesn't have any permissions configured yet.")
        return redirect('governance:dashboard')

    colleagues = OfficeAssignment.objects.filter(
        office=office, is_active=True
    ).exclude(user=request.user).select_related('user')

    colleagues_data = []
    for c in colleagues:
        u = c.user
        current = set(u.user_permissions.values_list('id', flat=True))
        granted_ids = {p.id for p in office_permissions if p.id in current}
        colleagues_data.append({
            'assignment': c,
            'user': u,
            'granted_ids': granted_ids,
        })

    if request.method == 'POST':
        target_user_id = request.POST.get('user_id')
        target_user = get_object_or_404(AuthUser, pk=target_user_id)

        is_member = OfficeAssignment.objects.filter(
            office=office, user=target_user, is_active=True
        ).exists()
        if not is_member:
            messages.error(request, "That user is not a member of your office.")
            return redirect('governance:delegation_home')

        submitted_ids = set(int(pid) for pid in request.POST.getlist('permissions') if pid.isdigit())
        allowed_ids = set(office_permissions.values_list('id', flat=True))
        to_grant = submitted_ids & allowed_ids

        current_user_perms = set(target_user.user_permissions.values_list('id', flat=True))
        outside_scope = current_user_perms - allowed_ids
        new_perms = outside_scope | to_grant

        granted = to_grant - current_user_perms
        revoked = (current_user_perms & allowed_ids) - to_grant

        target_user.user_permissions.set(Permission.objects.filter(id__in=new_perms))

        if granted:
            log_audit(request, 'permission_granted', office=office,
                      target_model='User', target_id=target_user.id,
                      object_repr=target_user.get_full_name(),
                      changes={'granted_ids': list(granted)})
        if revoked:
            log_audit(request, 'permission_revoked', office=office,
                      target_model='User', target_id=target_user.id,
                      object_repr=target_user.get_full_name(),
                      changes={'revoked_ids': list(revoked)})

        messages.success(
            request,
            f"✅ Updated {target_user.get_full_name()} "
            f"({len(granted)} granted, {len(revoked)} revoked)."
        )
        return redirect('governance:delegation_home')

    # Group permissions by app for the UI
    grouped = {}
    for p in office_permissions.select_related('content_type'):
        app_label = p.content_type.app_label
        grouped.setdefault(app_label, []).append(p)

    return render(request, 'governance/delegation_home.html', {
        'office': office,
        'can_manage_all': False,
        'colleagues_data': colleagues_data,
        'grouped_permissions': grouped,
        'office_permission_count': office_permissions.count(),
    })    
    
    
# ============================================================
# GRADUATION PROFILES — FULL FEATURE
# ============================================================

def _can_view_alumni(user):
    """Who can see alumni profiles."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if user.is_alumni:
        return True
    # Anyone with an active office = current EXCO
    if user.office_assignments.filter(is_active=True).exists():
        return True
    return False


@login_required
def graduation_list(request):
    """Public-to-alumni directory of all graduation profiles."""
    if not _can_view_alumni(request.user):
        messages.error(request, "Only NAMETS members and alumni can view the alumni directory.")
        return redirect('dashboards:dashboard')

    qs = GraduationProfile.objects.select_related('user').order_by(
        '-graduation_year', 'user__first_name', 'user__last_name'
    )

    year_filter = request.GET.get('year', '')
    dept_filter = request.GET.get('dept', '')
    office_filter = request.GET.get('office', '')
    query = request.GET.get('q', '').strip()

    if year_filter:
        qs = qs.filter(graduation_year=year_filter)
    if dept_filter:
        qs = qs.filter(department_name__icontains=dept_filter)
    if office_filter:
        # Match inside the JSON list of offices
        qs = qs.filter(offices_held__icontains=office_filter)
    if query:
        qs = qs.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
            | Q(department_name__icontains=query)
        )

    page = Paginator(qs, 24).get_page(request.GET.get('page'))

    # Available years for filter dropdown
    years = GraduationProfile.objects.values_list(
        'graduation_year', flat=True
    ).distinct().order_by('-graduation_year')

    # Available departments
    departments = GraduationProfile.objects.exclude(
        department_name=''
    ).values_list('department_name', flat=True).distinct().order_by('department_name')

    return render(request, 'governance/graduation_list.html', {
        'profiles': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'year_filter': year_filter,
        'dept_filter': dept_filter,
        'office_filter': office_filter,
        'query': query,
        'years': years,
        'departments': departments,
        'total_count': GraduationProfile.objects.count(),
    })


@login_required
def graduation_detail(request, pk):
    """View a single alumni profile."""
    profile = get_object_or_404(
        GraduationProfile.objects.select_related('user'),
        pk=pk
    )

    if not _can_view_alumni(request.user):
        messages.error(request, "Only NAMETS members and alumni can view alumni profiles.")
        return redirect('dashboards:dashboard')

    is_self = profile.user_id == request.user.id
    is_admin = request.user.is_superuser or (
        request.user.office_assignments.filter(
            is_active=True,
            office__name__icontains='wakeel'
        ).exists()
    ) or (
        request.user.office_assignments.filter(
            is_active=True,
            office__is_protected=True
        ).exists()
    )

    return render(request, 'governance/graduation_detail.html', {
        'profile': profile,
        'is_self': is_self,
        'can_edit': is_self or is_admin,
        'can_delete': is_admin,
    })


@login_required
def graduation_edit_own(request):
    """
    Shortcut for the current user to edit their own profile.
    Redirects to the edit page for their own profile.
    """
    profile = getattr(request.user, 'graduation_profile', None)
    if not profile:
        messages.error(request, "You don't have a graduation profile yet.")
        return redirect('dashboards:dashboard')
    return redirect('governance:graduation_edit', pk=profile.pk)


@login_required
def graduation_edit(request, pk):
    """Edit a graduation profile — self or admin."""
    profile = get_object_or_404(GraduationProfile, pk=pk)

    is_self = profile.user_id == request.user.id
    is_admin = request.user.is_superuser or (
        request.user.office_assignments.filter(
            is_active=True,
            office__name__icontains='wakeel'
        ).exists()
    ) or (
        request.user.office_assignments.filter(
            is_active=True,
            office__is_protected=True
        ).exists()
    )

    if not (is_self or is_admin):
        messages.error(request, "You can only edit your own graduation profile.")
        return redirect('governance:graduation_detail', pk=profile.pk)

    if request.method == 'POST':
        # Personal fields (self-editable)
        profile.final_message = request.POST.get('final_message', '').strip()
        profile.current_occupation = request.POST.get('current_occupation', '').strip()
        profile.current_location = request.POST.get('current_location', '').strip()

        # Social links
        social = {
            'linkedin': request.POST.get('linkedin', '').strip(),
            'twitter': request.POST.get('twitter', '').strip(),
            'instagram': request.POST.get('instagram', '').strip(),
            'facebook': request.POST.get('facebook', '').strip(),
            'whatsapp': request.POST.get('whatsapp', '').strip(),
            'github': request.POST.get('github', '').strip(),
        }
        profile.social_links = {k: v for k, v in social.items() if v}

        # Profile photo — delete old file if replacing
        if request.FILES.get('profile_photo'):
            if profile.profile_photo:
                profile.profile_photo.delete(save=False)
            profile.profile_photo = request.FILES['profile_photo']

        # Also allow updating contact info
        new_email = request.POST.get('email', '').strip()
        new_phone = request.POST.get('phone_number', '').strip()

        if new_email:
            profile.email = new_email
            # Optionally sync to User
            if is_self and profile.user.email != new_email:
                if not User.objects.filter(email__iexact=new_email).exclude(pk=profile.user.pk).exists():
                    profile.user.email = new_email
                    profile.user.username = new_email
                    profile.user.save(update_fields=['email', 'username'])
        if new_phone:
            profile.phone_number = new_phone
            if is_self:
                profile.user.phone_number = new_phone
                profile.user.save(update_fields=['phone_number'])

        # Admin-only fields
        if is_admin:
            gy = request.POST.get('graduation_year', '').strip()
            if gy.isdigit():
                profile.graduation_year = int(gy)
            profile.department_name = request.POST.get('department_name', '').strip()

        profile.save()

        # Audit log
        try:
            log_audit(
                request, 'update',
                target_model='GraduationProfile',
                target_id=profile.pk,
                object_repr=f"Updated profile: {profile.display_name}",
            )
        except Exception:
            pass

        messages.success(request, "✅ Your profile has been updated.")
        return redirect('governance:graduation_detail', pk=profile.pk)

    return render(request, 'governance/graduation_edit.html', {
        'profile': profile,
        'is_self': is_self,
        'is_admin': is_admin,
    })


@require_POST
@login_required
def graduation_delete(request, pk):
    """Admin-only: delete a graduation profile."""
    profile = get_object_or_404(GraduationProfile, pk=pk)

    is_admin = request.user.is_superuser or (
        request.user.office_assignments.filter(
            is_active=True,
            office__name__icontains='wakeel'
        ).exists()
    ) or (
        request.user.office_assignments.filter(
            is_active=True,
            office__is_protected=True
        ).exists()
    )

    if not is_admin:
        messages.error(request, "Only the Wakeel or ICT Head can delete alumni profiles.")
        return redirect('governance:graduation_detail', pk=profile.pk)

    name = profile.display_name
    profile.delete()

    try:
        log_audit(
            request, 'delete',
            target_model='GraduationProfile',
            target_id=pk,
            object_repr=f"Deleted profile: {name}",
        )
    except Exception:
        pass

    messages.success(request, f"🗑️ Profile for “{name}” has been deleted.")
    return redirect('governance:graduation_list')


@login_required
def my_graduation_profile(request):
    """
    Redirect helper — used by the sidebar for alumni.
    If the user has a profile, send them to it. Otherwise, error.
    """
    profile = getattr(request.user, 'graduation_profile', None)
    if not profile:
        messages.info(
            request,
            "You don't have an alumni profile yet. It's created automatically when your session's EXCO dissolves."
        )
        return redirect('dashboards:dashboard')
    return redirect('governance:graduation_detail', pk=profile.pk)    
    
    
# ============================================================
# SESSION DOCUMENTS
# ============================================================

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST


def _user_can_view_session_docs(user):
    """Alumni + current EXCO + superusers."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if getattr(user, 'is_alumni', False):
        return True
    return user.office_assignments.filter(is_active=True).exists()


def _user_can_manage_session_docs(user):
    """Superuser, or any active office containing 'wakeel', 'ict', or 'secretary'."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if user.has_perm('governance.add_sessiondocument'):
        return True
    return user.office_assignments.filter(
        is_active=True,
        office__name__icontains='wakeel',
    ).exists() or user.office_assignments.filter(
        is_active=True,
        office__name__icontains='ict',
    ).exists() or user.office_assignments.filter(
        is_active=True,
        office__name__icontains='secretary',
    ).exists()


@login_required
def session_document_list(request):
    """Archive of session documents — members and alumni."""
    if not _user_can_view_session_docs(request.user):
        messages.error(request, "Session archives are only available to NAMETS members and alumni.")
        return redirect('dashboards:dashboard')

    qs = SessionDocument.objects.filter(is_published=True).select_related('uploaded_by')

    # Filters
    q = request.GET.get('q', '').strip()
    type_filter = request.GET.get('type', '').strip()
    year_filter = request.GET.get('year', '').strip()

    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(session_label__icontains=q)
        )
    if type_filter:
        qs = qs.filter(document_type=type_filter)
    if year_filter and year_filter.isdigit():
        qs = qs.filter(session_year=int(year_filter))

    # Featured first, then the model's default ordering
    qs = qs.order_by('-is_featured', '-session_year', 'order', '-uploaded_at')

    # Available years for the filter dropdown
    years = (
        SessionDocument.objects
        .filter(is_published=True)
        .values_list('session_year', flat=True)
        .distinct()
        .order_by('-session_year')
    )

    page = Paginator(qs, 12).get_page(request.GET.get('page'))

    # Group by session for a nice display
    grouped = {}
    for doc in page:
        grouped.setdefault(doc.session_label, []).append(doc)

    stats = {
        'total_documents': SessionDocument.objects.filter(is_published=True).count(),
        'total_sessions': SessionDocument.objects.filter(is_published=True)
                          .values('session_year').distinct().count(),
        'total_magazines': SessionDocument.objects.filter(
            is_published=True, document_type=SessionDocument.TYPE_MAGAZINE
        ).count(),
        'total_photos': SessionDocument.objects.filter(
            is_published=True, document_type=SessionDocument.TYPE_PHOTO_ALBUM
        ).count(),
    }

    return render(request, 'governance/session_document_list.html', {
        'documents': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'grouped_by_session': grouped,
        'q': q,
        'type_filter': type_filter,
        'year_filter': year_filter,
        'years': years,
        'type_choices': SessionDocument.TYPE_CHOICES,
        'can_manage': _user_can_manage_session_docs(request.user),
        **stats,
    })


@login_required
def session_document_detail(request, pk):
    """View a single session document."""
    if not _user_can_view_session_docs(request.user):
        messages.error(request, "Session archives are only available to NAMETS members and alumni.")
        return redirect('dashboards:dashboard')

    doc = get_object_or_404(
        SessionDocument.objects.select_related('uploaded_by'),
        pk=pk,
    )

    # Drafts only visible to managers
    if not doc.is_published and not _user_can_manage_session_docs(request.user):
        messages.error(request, "This document is not published yet.")
        return redirect('governance:session_document_list')

    # Related documents from the same session
    related = SessionDocument.objects.filter(
        session_year=doc.session_year,
        is_published=True,
    ).exclude(pk=doc.pk).order_by('order', '-uploaded_at')[:6]

    return render(request, 'governance/session_document_detail.html', {
        'doc': doc,
        'related': related,
        'can_manage': _user_can_manage_session_docs(request.user),
    })


@login_required
def session_document_manage(request):
    """Manager dashboard — all documents, published and drafts."""
    if not _user_can_manage_session_docs(request.user):
        messages.error(request, "You don't have permission to manage session documents.")
        return redirect('governance:session_document_list')

    qs = SessionDocument.objects.select_related('uploaded_by').order_by(
        '-session_year', 'order', '-uploaded_at'
    )

    q = request.GET.get('q', '').strip()
    type_filter = request.GET.get('type', '').strip()
    publish_filter = request.GET.get('published', '').strip()

    if q:
        qs = qs.filter(
            Q(title__icontains=q) | Q(description__icontains=q)
        )
    if type_filter:
        qs = qs.filter(document_type=type_filter)
    if publish_filter == 'published':
        qs = qs.filter(is_published=True)
    elif publish_filter == 'draft':
        qs = qs.filter(is_published=False)

    page = Paginator(qs, 20).get_page(request.GET.get('page'))

    return render(request, 'governance/session_document_manage.html', {
        'documents': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'q': q,
        'type_filter': type_filter,
        'publish_filter': publish_filter,
        'type_choices': SessionDocument.TYPE_CHOICES,
        'total_all': SessionDocument.objects.count(),
        'total_published': SessionDocument.objects.filter(is_published=True).count(),
        'total_drafts': SessionDocument.objects.filter(is_published=False).count(),
    })


@login_required
def session_document_form(request, pk=None):
    """Upload/edit a session document."""
    if not _user_can_manage_session_docs(request.user):
        messages.error(request, "You don't have permission to manage session documents.")
        return redirect('governance:session_document_list')

    doc = get_object_or_404(SessionDocument, pk=pk) if pk else None

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        session_label = request.POST.get('session_label', '').strip()
        session_year_raw = request.POST.get('session_year', '').strip()

        # Validation
        if not title:
            messages.error(request, "Title is required.")
        elif not session_label:
            messages.error(request, "Session label is required (e.g. 2023/2024).")
        elif not session_year_raw.isdigit():
            messages.error(request, "Session year must be a number (e.g. 2024).")
        else:
            if doc is None:
                doc = SessionDocument(uploaded_by=request.user)

            doc.title = title
            doc.description = request.POST.get('description', '').strip()
            doc.document_type = request.POST.get(
                'document_type', SessionDocument.TYPE_MAGAZINE
            )
            doc.session_label = session_label
            doc.session_year = int(session_year_raw)
            doc.external_cover_url = request.POST.get('external_cover_url', '').strip()
            doc.external_file_url = request.POST.get('external_file_url', '').strip()
            doc.external_file_label = (
                request.POST.get('external_file_label', '').strip()
                or 'Open document'
            )
            doc.is_published = 'is_published' in request.POST
            doc.is_featured = 'is_featured' in request.POST

            order_raw = request.POST.get('order', '0').strip()
            doc.order = int(order_raw) if order_raw.isdigit() else 0

            # Cover upload — overwrite only if a new file is provided
            new_cover = request.FILES.get('cover_image')
            if new_cover:
                if doc.pk and doc.cover_image:
                    try:
                        doc.cover_image.delete(save=False)
                    except Exception:
                        pass
                doc.cover_image = new_cover

            # Document file upload
            new_file = request.FILES.get('file')
            if new_file:
                if doc.pk and doc.file:
                    try:
                        doc.file.delete(save=False)
                    except Exception:
                        pass
                doc.file = new_file

            if not doc.external_file_url and not doc.file:
                messages.error(request, "Please upload a file or provide an external link.")
            else:
                doc.save()
                messages.success(request, f"✅ “{doc.title}” saved.")
                return redirect('governance:session_document_manage')

    return render(request, 'governance/session_document_form.html', {
        'doc': doc,
        'type_choices': SessionDocument.TYPE_CHOICES,
    })


@login_required
def session_document_delete(request, pk):
    """Delete a session document."""
    if not _user_can_manage_session_docs(request.user):
        messages.error(request, "You don't have permission to delete session documents.")
        return redirect('governance:session_document_list')

    doc = get_object_or_404(SessionDocument, pk=pk)

    if request.method == 'POST':
        title = doc.title

        # Clean up uploaded files
        for field in (doc.file, doc.cover_image):
            try:
                if field:
                    field.delete(save=False)
            except Exception:
                pass

        doc.delete()
        messages.success(request, f"🗑️ “{title}” removed.")
        return redirect('governance:session_document_manage')

    return render(request, 'governance/session_document_confirm_delete.html', {'doc': doc})


@login_required
def session_document_toggle_publish(request, pk):
    """Quick publish/unpublish toggle (POST only)."""
    if not _user_can_manage_session_docs(request.user):
        return JsonResponse({'ok': False, 'error': 'Permission denied'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    doc = get_object_or_404(SessionDocument, pk=pk)
    doc.is_published = not doc.is_published
    doc.save(update_fields=['is_published'])

    return JsonResponse({'ok': True, 'is_published': doc.is_published})    
    
    
    
    
    
    
    