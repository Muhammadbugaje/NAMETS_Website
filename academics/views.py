# ============================================================
# IMPORTS
# ============================================================
import json
import hmac
import hashlib
from datetime import datetime, timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, Http404, JsonResponse
from django.db.models import Q, Sum, Count, Avg
from django.core.paginator import Paginator
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.forms import modelform_factory

import openpyxl
from openpyxl.styles import PatternFill, Font
from openpyxl.utils import get_column_letter

from cloudinary.utils import cloudinary_url

from core.models import SiteSettings
from core.email_utils import send_templated_email
from core.importers.spec import ColumnSpec, ImportSpec
from core.importers.excel_io import build_export_xlsx

# Reuse Business's payment & ledger infrastructure
from business.models import BankAccount, Transaction, record_payment_to_ledger
from business.views import _verify_paystack_reference, generate_paystack_reference

from . import selectors
from .models import (
    Course, Tutor, Session, Material, Evaluation, Result,
    TutorEvaluation, TimetableEntry, IslamiyyaCourse,
    IslamiyyaSettings, IslamiyyaRegistration,
    UserResourceSubmission, CompetitionResult,
    AttendanceSession, AttendanceRecord, CBTCourse, QuestionBank,
)
from .forms import (
    TutorEvaluationForm, TimetableUploadForm, ResourceSubmissionForm,
    IslamiyyaRegistrationForm, CheckStatusForm, ExcelUploadForm,
    TutorForm, CourseForm, SessionForm, MaterialForm, EvaluationForm,
    TimetableForm, IslamiyyaCourseForm, IslamiyyaSettingsForm,
    IslamiyyaRegistrationAdminForm, CompetitionResultForm,
    AttendanceSessionForm,
)


# ============================================================
# HELPER: PAYSTACK AMOUNT (in kobo)
# ============================================================

def _to_kobo(amount):
    try:
        return int(float(amount) * 100)
    except Exception:
        return 0


# ============================================================
# ============================================================
# PART 1 — EXISTING PUBLIC VIEWS (unchanged)
# ============================================================
# ============================================================

def course_list(request):
    tutorial_courses = selectors.get_active_courses(course_type='tutorial')
    islamiyya_courses = selectors.get_active_courses(course_type='islamiyya')
    tutorial_sessions = selectors.get_upcoming_sessions(course_type='tutorial')
    islamiyya_sessions = selectors.get_upcoming_sessions(course_type='islamiyya')

    upcoming_sessions = list(tutorial_sessions) + list(islamiyya_sessions)
    upcoming_sessions.sort(key=lambda s: (s.date, s.start_time))

    context = {
        'tutorial_count': tutorial_courses.count(),
        'islamiyya_count': islamiyya_courses.count(),
        'tutorial_sessions_count': tutorial_sessions.count(),
        'islamiyya_sessions_count': islamiyya_sessions.count(),
        'upcoming_sessions': upcoming_sessions,
    }
    return render(request, 'academics/course_list.html', context)


def course_detail(request, slug):
    course = get_object_or_404(Course, slug=slug, is_active=True)
    sessions = selectors.get_upcoming_sessions(course)
    materials = selectors.get_course_materials(course)
    evaluations = selectors.get_course_evaluations(course)
    settings_obj = SiteSettings.objects.first()
    context = {
        'course': course,
        'sessions': sessions,
        'materials': materials,
        'evaluations': evaluations,
        'settings': settings_obj,
    }
    return render(request, 'academics/course_detail.html', context)


def course_results(request, slug):
    course = get_object_or_404(Course, slug=slug, is_active=True)
    search_query = request.GET.get('q', '').strip()
    results = selectors.get_results_for_course(course, '')
    if search_query:
        results = results.filter(
            Q(student_name__icontains=search_query) |
            Q(registration_number__icontains=search_query)
        )
    exam = Evaluation.objects.filter(course=course, is_active=True).first()
    context = {
        'course': course,
        'results': results,
        'search_query': search_query,
        'total_mark': exam.total_marks if exam else None,
    }
    return render(request, 'academics/course_results.html', context)


def student_search(request):
    query = request.GET.get('q', '')
    results = None
    summary = None
    if query:
        results = selectors.search_student_results(query)
        summary = selectors.get_student_summary(query)
    context = {
        'query': query,
        'results': results,
        'summary': summary,
    }
    return render(request, 'academics/student_search.html', context)


def materials_list(request, slug):
    course = get_object_or_404(Course, slug=slug, is_active=True)
    materials = Material.objects.filter(course=course, is_active=True)
    return render(request, 'academics/materials_list.html', {
        'course': course,
        'materials': materials,
    })


def exam_list(request, slug=None):
    exams = Evaluation.objects.filter(is_active=True).select_related('course').order_by('-date')
    course_slug = request.GET.get('course')
    if course_slug:
        exams = exams.filter(course__slug=course_slug)
    context = {
        'exams': exams,
        'courses': Course.objects.filter(is_active=True),
    }
    return render(request, 'academics/exams.html', context)


def tutorial_list(request):
    courses = selectors.get_active_courses(course_type='tutorial')
    timetable_level1 = TimetableEntry.objects.filter(
        entry_type='tutorial', level='level1', is_active=True
    ).order_by('day', 'time_start')
    timetable_level2 = TimetableEntry.objects.filter(
        entry_type='tutorial', level='level2', is_active=True
    ).order_by('day', 'time_start')
    return render(request, 'academics/tutorial_list.html', {
        'courses': courses,
        'timetable_level1': timetable_level1,
        'timetable_level2': timetable_level2,
    })


def islamia_list(request):
    courses = selectors.get_active_courses(course_type='islamiyya')
    timetable = TimetableEntry.objects.filter(
        entry_type='islamiyya', is_active=True
    ).order_by('day', 'time_start')
    return render(request, 'academics/islamiyyah_list.html', {
        'courses': courses,
        'timetable': timetable,
    })


def exam_detail(request, exam_id):
    exam = get_object_or_404(Evaluation, id=exam_id, is_active=True)
    results = exam.results.all()
    student_name = request.GET.get('student', '')
    if student_name:
        results = results.filter(student_name__icontains=student_name)
    context = {
        'exam': exam,
        'results': results,
        'student_name': student_name,
    }
    return render(request, 'academics/exam_detail.html', context)


def all_results(request):
    course_id = request.GET.get('course')
    reg_no = request.GET.get('reg_no')
    student_name = request.GET.get('student_name')
    results = selectors.get_all_results(course_id, reg_no, student_name)
    courses = Course.objects.filter(is_active=True)
    context = {
        'results': results,
        'courses': courses,
        'selected_course': course_id,
        'reg_no': reg_no,
        'student_name': student_name,
    }
    return render(request, 'academics/all_results.html', context)


def evaluate_tutor(request, slug):
    settings_obj = SiteSettings.objects.first()
    if not settings_obj or not settings_obj.tutor_evaluations_open:
        return render(request, 'academics/evaluation_closed.html', {'type': 'tutor'})

    course = get_object_or_404(Course, slug=slug, is_active=True)
    if request.method == 'POST':
        form = TutorEvaluationForm(request.POST, course=course)
        if form.is_valid():
            evaluation = form.save(commit=False)
            evaluation.course = course
            evaluation.save()
            messages.success(request, 'Thank you for your feedback!')
            return redirect('academics:course_detail', slug=course.slug)
    else:
        form = TutorEvaluationForm(course=course)
    return render(request, 'academics/evaluate_tutor.html', {
        'form': form,
        'course': course,
        'intro': settings_obj.evaluation_intro_text,
    })


def download_material(request, material_id):
    material = get_object_or_404(Material, id=material_id, is_active=True)
    if material.file:
        options = {'resource_type': 'image', 'flags': 'attachment'}
        download_url, _ = cloudinary_url(material.file.public_id, **options)
        return redirect(download_url)
    elif material.drive_link:
        return redirect(material.drive_link)
    raise Http404("No file attached to this material.")


def parse_time_range(time_range_str):
    parts = time_range_str.replace(' ', '').split('-')
    if len(parts) != 2:
        raise ValueError("Invalid time range format (expected HH-HH or HH:MM-HH:MM)")
    start_str, end_str = parts
    if ':' not in start_str:
        start_str += ':00'
    if ':' not in end_str:
        end_str += ':00'
    start = datetime.strptime(start_str, '%H:%M').time()
    end = datetime.strptime(end_str, '%H:%M').time()
    return start, end


def upload_timetable_excel(request):
    if request.method == 'POST':
        form = TimetableUploadForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['excel_file']
            wb = openpyxl.load_workbook(excel_file)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if len(rows) < 2:
                messages.error(request, "File is empty or has only headers.")
                return redirect('admin:academics_timetableentry_changelist')
            data_rows = rows[1:]
            created_count = 0
            errors = []
            for idx, row in enumerate(data_rows, start=2):
                if not any(row):
                    continue
                if len(row) < 6:
                    errors.append(f"Row {idx}: Not enough columns (found {len(row)}, need 6)")
                    continue
                day = row[0]
                time_range = row[1]
                course_name = row[2]
                venue = row[3]
                entry_type = row[4]
                level = row[5] if len(row) > 5 else 'level1'
                try:
                    day = int(day)
                    if day not in range(1, 8):
                        errors.append(f"Row {idx}: Day must be 1-7, got {day}")
                        continue
                except (ValueError, TypeError):
                    errors.append(f"Row {idx}: Invalid day value '{day}'")
                    continue
                try:
                    start, end = parse_time_range(str(time_range).strip())
                except ValueError as e:
                    errors.append(f"Row {idx}: {e}")
                    continue
                entry_type_clean = str(entry_type).strip().lower()
                if entry_type_clean not in ['tutorial', 'islamiyya']:
                    errors.append(f"Row {idx}: entry_type must be 'tutorial' or 'islamiyya'")
                    continue
                level_clean = str(level).strip().lower()
                if level_clean not in ['level1', 'level2']:
                    errors.append(f"Row {idx}: level must be 'level1' or 'level2'")
                    continue
                TimetableEntry.objects.create(
                    day=day, time_start=start, time_end=end,
                    course_name=str(course_name).strip()[:200],
                    venue=str(venue).strip()[:200] if venue else '',
                    entry_type=entry_type_clean, level=level_clean, is_active=True,
                )
                created_count += 1
            if created_count > 0:
                messages.success(request, f"Successfully imported {created_count} timetable entries.")
            if errors:
                messages.error(request, f"Failed to import {len(errors)} rows:")
                for err in errors[:5]:
                    messages.error(request, err)
                if len(errors) > 5:
                    messages.error(request, f"... and {len(errors)-5} more errors.")
            return redirect('admin:academics_timetableentry_changelist')
    else:
        form = TimetableUploadForm()
    return render(request, 'admin/academics/timetable_upload.html', {
        'form': form,
        'title': 'Upload Timetable Excel',
    })


# ---------- ISLAMIYYA PUBLIC ----------

def _get_current_islamiyya_settings():
    """Return the active IslamiyyaSettings, or None."""
    return IslamiyyaSettings.objects.filter(is_active=True).first()


def islamiyya_registration_open(request):
    """
    Registration is open ONLY IF:
      1. The global master switch is on (core.SiteSettings)
      2. The active session's window/toggle allows it (academics.IslamiyyaSettings)
    """
    from core.models import SiteSettings
    site = SiteSettings.objects.first()
    global_open = bool(site and site.islamiyya_registration_open)

    current = _get_current_islamiyya_settings()
    session_open = bool(current and current.is_currently_open)

    return global_open and session_open


def islamiyya_register(request):
    current = _get_current_islamiyya_settings()
    if not current or not current.is_currently_open:
        return render(request, 'academics/islamiyya_registration_closed.html', {
            'settings': current,
        })

    if request.method == 'POST':
        form = IslamiyyaRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            registration = form.save(commit=False)
            registration.session_settings = current
            registration.save()
            form.save_m2m()

            request.session['islamiyya_app_id'] = registration.application_id

            # If a fee is set, go straight to payment
            if current.registration_fee > 0:
                messages.info(
                    request,
                    f"Registration received. Please complete payment of "
                    f"₦{current.registration_fee:,.2f} to unlock your WhatsApp group link."
                )
                return redirect('academics:islamiyya_pay', app_id=registration.application_id)

            messages.success(request, 'Registration successful!')
            return redirect('academics:islamiyya_dashboard')
    else:
        form = IslamiyyaRegistrationForm()
    return render(request, 'academics/islamiyya_register.html', {
        'form': form,
        'settings': current,
    })


def islamiyya_check_status(request):
    if request.method == 'POST':
        form = CheckStatusForm(request.POST)
        if form.is_valid():
            identifier = form.cleaned_data['identifier']
            registration = (
                IslamiyyaRegistration.objects.filter(email__iexact=identifier).first()
                or IslamiyyaRegistration.objects.filter(registration_number__iexact=identifier).first()
                or IslamiyyaRegistration.objects.filter(application_id__iexact=identifier).first()
            )
            if registration:
                request.session['islamiyya_app_id'] = registration.application_id
                return redirect('academics:islamiyya_dashboard')
            messages.error(request, 'No registration found with that email, ID, or registration number.')
            return redirect('academics:islamiyya_check_status')
    else:
        form = CheckStatusForm()
    return render(request, 'academics/islamiyya_check_status.html', {'form': form})


def islamiyya_dashboard(request):
    app_id = request.session.get('islamiyya_app_id')
    if not app_id:
        messages.error(request, 'Please check your status first.')
        return redirect('academics:islamiyya_check_status')

    registration = get_object_or_404(IslamiyyaRegistration, application_id=app_id)

    # Fallback WhatsApp link from core SiteSettings (global default)
    from core.models import SiteSettings
    site = SiteSettings.objects.first()
    global_whatsapp = site.islamiyya_whatsapp_link if site else None

    # Determine WhatsApp visibility
    whatsapp_link = None
    expired = False
    if registration.is_paid:
        # Priority: registration snapshot → session override → global fallback
        whatsapp_link = (
            registration.whatsapp_link
            or (registration.session_settings.whatsapp_group_link
                if registration.session_settings else None)
            or global_whatsapp
        )
        # 1-year expiry from verification
        if registration.verified_at and registration.verified_at < timezone.now() - timedelta(days=365):
            whatsapp_link = None
            expired = True

    return render(request, 'academics/islamiyya_dashboard.html', {
        'registration': registration,
        'whatsapp_link': whatsapp_link,
        'expired': expired,
        'settings': registration.session_settings,
    })

def resources_page(request):
    query = request.GET.get('q', '')
    resources = UserResourceSubmission.objects.filter(status='approved').order_by('-submitted_at')
    if query:
        resources = resources.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
    paginator = Paginator(resources, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'academics/resources.html', {
        'page_obj': page_obj,
        'query': query,
    })


def submit_resource(request):
    if request.method == 'POST':
        form = ResourceSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Thank you! Your resource has been submitted and will be reviewed by the admin.')
            return redirect('academics:submit_resource')
    else:
        form = ResourceSubmissionForm()
    return render(request, 'academics/submit_resource.html', {'form': form})


def download_resource(request, pk):
    resource = get_object_or_404(UserResourceSubmission, pk=pk, status='approved')
    resource.download_count += 1
    resource.save(update_fields=['download_count'])
    return redirect(resource.file.url)


def competition_results(request):
    queryset = CompetitionResult.objects.filter(is_active=True)
    selected_event = request.GET.get('event', '')
    selected_category = request.GET.get('category', '')
    selected_year = request.GET.get('year', '')

    if selected_event:
        queryset = queryset.filter(event_name=selected_event)
    if selected_category:
        queryset = queryset.filter(category=selected_category)
    if selected_year:
        queryset = queryset.filter(year=selected_year)

    event_choices = CompetitionResult.objects.filter(is_active=True).values_list('event_name', flat=True).distinct().order_by('event_name')
    category_choices = CompetitionResult.objects.filter(is_active=True).values_list('category', flat=True).distinct().exclude(category='').order_by('category')
    year_choices = CompetitionResult.objects.filter(is_active=True).values_list('year', flat=True).distinct().exclude(year='').order_by('-year')

    events = {}
    for r in queryset:
        key = f"{r.event_name} – {r.category}" if r.category else r.event_name
        events.setdefault(key, []).append(r)

    return render(request, 'academics/competition_results.html', {
        'events': events,
        'event_choices': event_choices,
        'category_choices': category_choices,
        'year_choices': year_choices,
        'selected_event': selected_event,
        'selected_category': selected_category,
        'selected_year': selected_year,
    })


# ============================================================
# ============================================================
# PART 2 — ISLAMIYYA PAYMENT FLOW
# ============================================================
# ============================================================

def islamiyya_pay(request, app_id):
    """
    Public payment page. Guest can pay from here.
    Uses Paystack, records a Transaction, marks registration paid.
    """
    registration = get_object_or_404(IslamiyyaRegistration, application_id=app_id)

    if registration.is_paid:
        messages.info(request, "This registration is already paid.")
        return redirect('academics:islamiyya_dashboard')

    current = registration.session_settings or _get_current_islamiyya_settings()
    if not current or not current.account:
        messages.error(
            request,
            "Payment is currently unavailable. Please contact the Islamiyya office."
        )
        return redirect('academics:islamiyya_dashboard')

    paystack_public_key = getattr(settings, 'PAYSTACK_PUBLIC_KEY', '')
    if not paystack_public_key:
        messages.error(request, "Payment gateway is not configured.")
        return redirect('academics:islamiyya_dashboard')

    reference = generate_paystack_reference()
    registration.payment_reference = reference
    registration.save(update_fields=['payment_reference'])

    return render(request, 'academics/islamiyya_pay.html', {
        'registration': registration,
        'settings': current,
        'paystack_public_key': paystack_public_key,
        'reference': reference,
        'amount': _to_kobo(current.registration_fee),
        'amount_display': f"{current.registration_fee:,.2f}",
        'callback_url': request.build_absolute_uri(reverse('academics:islamiyya_paystack_callback')),
    })


def islamiyya_paystack_callback(request):
    """
    Returns from Paystack. Verifies payment directly (webhook fallback).
    No @login_required — guests must reach this.
    """
    reference = request.GET.get('reference', '').strip()
    if not reference:
        messages.error(request, "No payment reference found.")
        return redirect('academics:islamiyya_check_status')

    verified = _verify_paystack_reference(reference)
    registration = IslamiyyaRegistration.objects.filter(payment_reference=reference).first()
    if not registration:
        messages.error(request, "We couldn't find your registration.")
        return redirect('academics:islamiyya_check_status')

    if registration.is_paid:
        messages.success(request, "✅ Payment already confirmed. Welcome to Islamiyya!")
        return redirect('academics:islamiyya_dashboard')

    if not verified:
        messages.warning(request, "Payment could not be verified yet. Please try again in a moment.")
        return redirect('academics:islamiyya_dashboard')

    # Amount from Paystack (in kobo → naira)
    paid_amount = float(verified.get('amount', 0)) / 100
    _complete_islamiyya_payment(registration, paid_amount, method='paystack', reference=reference)

    messages.success(request, "✅ Payment successful! Welcome to Islamiyya — your WhatsApp group link is now available.")
    return redirect('academics:islamiyya_dashboard')


def _complete_islamiyya_payment(registration, amount, method, reference='', verified_by=None):
    """
    Central helper: mark registration paid, record to ledger,
    snapshot WhatsApp link, save everything atomically.
    """
    settings_obj = registration.session_settings
    account = settings_obj.account if settings_obj else None

    registration.mark_paid(
        amount=amount,
        method=method,
        reference=reference,
        verified_by=verified_by,
    )

    if account and amount > 0:
        record_payment_to_ledger(
            amount=amount,
            category='islamiyya_revenue',
            description=(
                f"Islamiyya registration {registration.application_id}: {registration.name} "
                f"({settings_obj.academic_session if settings_obj else '—'})"
            ),
            account=account,
            user=verified_by,
        )


# ============================================================
# ============================================================
# PART 3 — EXCO ADMIN — DASHBOARD
# ============================================================
# ============================================================

@login_required
def admin_dashboard(request):
    """Academics EXCO landing page."""
    if not (
        request.user.has_perm('academics.view_course')
        or request.user.has_perm('academics.view_islamiyyaregistration')
        or request.user.has_perm('academics.view_cbtcourse')
        or request.user.has_perm('academics.view_questionbank')
    ):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    from django.db.models import Sum, F

    # ---------- Core KPIs ----------
    total_courses = Course.objects.filter(is_active=True).count()
    total_tutors = Tutor.objects.filter(is_active=True).count()
    upcoming_sessions = Session.objects.filter(
        is_active=True, date__gte=timezone.now().date()
    ).count()
    pending_resources = UserResourceSubmission.objects.filter(status='pending').count()

    # ---------- Islamiyya snapshot ----------
    current_islamiyya = _get_current_islamiyya_settings()
    if current_islamiyya:
        islamiyya_paid = current_islamiyya.paid_count
        islamiyya_pending = current_islamiyya.pending_count
        islamiyya_collected = current_islamiyya.total_collected
        islamiyya_fee = current_islamiyya.registration_fee
    else:
        islamiyya_paid = islamiyya_pending = islamiyya_collected = islamiyya_fee = 0

    # ---------- CBT snapshot ----------
    cbt_enabled = False
    try:
        from core.models import SiteSettings
        site = SiteSettings.objects.first()
        cbt_enabled = bool(site and getattr(site, 'cbt_enabled', False))
    except Exception:
        cbt_enabled = False

    cbt_courses = 0
    if request.user.has_perm('academics.view_cbtcourse'):
        cbt_courses = CBTCourse.objects.filter(is_active=True).count()

    cbt_questions_total = 0
    cbt_questions_active = 0
    cbt_low_quality = 0
    cbt_attempts_total = 0
    if request.user.has_perm('academics.view_questionbank'):
        qs_all = QuestionBank.objects.all()
        qs_active = qs_all.filter(is_active=True)
        cbt_questions_total = qs_all.count()
        cbt_questions_active = qs_active.count()
        cbt_low_quality = qs_active.filter(
            times_answered__gte=5,
            times_correct__lt=F('times_answered') * 0.4,
        ).count()
        agg = QuestionBank.objects.aggregate(t=Sum('times_answered'))
        cbt_attempts_total = agg['t'] or 0

    # ---------- Recent activity ----------
    recent_registrations = IslamiyyaRegistration.objects.all().order_by('-submitted_at')[:5]
    recent_submissions = UserResourceSubmission.objects.all().order_by('-submitted_at')[:5]
    recent_evaluations = TutorEvaluation.objects.all().order_by('-submitted_at')[:5]

    return render(request, 'academics/admin/dashboard.html', {
        # Core
        'total_courses': total_courses,
        'total_tutors': total_tutors,
        'upcoming_sessions': upcoming_sessions,
        'pending_resources': pending_resources,
        # Islamiyya
        'current_islamiyya': current_islamiyya,
        'islamiyya_paid': islamiyya_paid,
        'islamiyya_pending': islamiyya_pending,
        'islamiyya_collected': islamiyya_collected,
        'islamiyya_fee': islamiyya_fee,
        # CBT
        'cbt_enabled': cbt_enabled,
        'cbt_courses': cbt_courses,
        'cbt_questions_total': cbt_questions_total,
        'cbt_questions_active': cbt_questions_active,
        'cbt_low_quality': cbt_low_quality,
        'cbt_attempts_total': cbt_attempts_total,
        # Recent activity
        'recent_registrations': recent_registrations,
        'recent_submissions': recent_submissions,
        'recent_evaluations': recent_evaluations,
    })

# ============================================================
# PART 4 — EXCO ADMIN — COURSES
# ============================================================

@login_required
def admin_course_list(request):
    if not request.user.has_perm('academics.view_course'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    query = request.GET.get('q', '')
    type_filter = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')

    qs = Course.objects.all().order_by('name')
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if type_filter:
        qs = qs.filter(course_type=type_filter)
    if status_filter == 'active':
        qs = qs.filter(is_active=True)
    elif status_filter == 'inactive':
        qs = qs.filter(is_active=False)

    page = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'academics/admin/course_list.html', {
        'courses': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'query': query,
        'type_filter': type_filter,
        'status_filter': status_filter,
    })


@login_required
def admin_course_create(request):
    if not request.user.has_perm('academics.add_course'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_course_list')

    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"✅ Course '{obj.name}' created.")
            return redirect('academics:admin_course_list')
    else:
        form = CourseForm()
    return render(request, 'academics/admin/course_form.html', {
        'form': form, 'title': 'Add Course', 'button_text': 'Create Course',
    })


@login_required
def admin_course_edit(request, pk):
    obj = get_object_or_404(Course, pk=pk)
    if not request.user.has_perm('academics.change_course'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_course_list')

    if request.method == 'POST':
        form = CourseForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Course '{obj.name}' updated.")
            return redirect('academics:admin_course_list')
    else:
        form = CourseForm(instance=obj)
    return render(request, 'academics/admin/course_form.html', {
        'form': form, 'course': obj, 'title': 'Edit Course', 'button_text': 'Update Course',
    })


@login_required
@require_POST
def admin_course_delete(request, pk):
    obj = get_object_or_404(Course, pk=pk)
    if not request.user.has_perm('academics.delete_course'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_course_list')
    name = obj.name
    obj.delete()
    messages.success(request, f"🗑️ Course '{name}' deleted.")
    return redirect('academics:admin_course_list')


# ============================================================
# PART 5 — EXCO ADMIN — TUTORS
# ============================================================

@login_required
def admin_tutor_list(request):
    if not request.user.has_perm('academics.view_tutor'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    qs = Tutor.objects.all().order_by('name')
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(email__icontains=query))
    if status_filter == 'active':
        qs = qs.filter(is_active=True)
    elif status_filter == 'inactive':
        qs = qs.filter(is_active=False)

    page = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'academics/admin/tutor_list.html', {
        'tutors': page, 'page_obj': page, 'is_paginated': page.has_other_pages(),
        'query': query, 'status_filter': status_filter,
    })


@login_required
def admin_tutor_create(request):
    if not request.user.has_perm('academics.add_tutor'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_tutor_list')

    if request.method == 'POST':
        form = TutorForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"✅ Tutor '{obj.name}' created.")
            return redirect('academics:admin_tutor_list')
    else:
        form = TutorForm()
    return render(request, 'academics/admin/tutor_form.html', {
        'form': form, 'title': 'Add Tutor', 'button_text': 'Create Tutor',
    })


@login_required
def admin_tutor_edit(request, pk):
    obj = get_object_or_404(Tutor, pk=pk)
    if not request.user.has_perm('academics.change_tutor'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_tutor_list')

    if request.method == 'POST':
        form = TutorForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Tutor '{obj.name}' updated.")
            return redirect('academics:admin_tutor_list')
    else:
        form = TutorForm(instance=obj)
    return render(request, 'academics/admin/tutor_form.html', {
        'form': form, 'tutor': obj, 'title': 'Edit Tutor', 'button_text': 'Update Tutor',
    })


@login_required
@require_POST
def admin_tutor_delete(request, pk):
    obj = get_object_or_404(Tutor, pk=pk)
    if not request.user.has_perm('academics.delete_tutor'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_tutor_list')
    name = obj.name
    obj.delete()
    messages.success(request, f"🗑️ Tutor '{name}' deleted.")
    return redirect('academics:admin_tutor_list')


# ============================================================
# PART 6 — EXCO ADMIN — SESSIONS
# ============================================================

@login_required
def admin_session_list(request):
    if not request.user.has_perm('academics.view_session'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    qs = Session.objects.select_related('course').order_by('-date')
    course_filter = request.GET.get('course', '')
    if course_filter:
        qs = qs.filter(course_id=course_filter)

    page = Paginator(qs, 30).get_page(request.GET.get('page'))
    return render(request, 'academics/admin/session_list.html', {
        'sessions': page, 'page_obj': page, 'is_paginated': page.has_other_pages(),
        'courses': Course.objects.filter(is_active=True),
        'course_filter': course_filter,
    })


@login_required
def admin_session_create(request):
    if not request.user.has_perm('academics.add_session'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_session_list')

    if request.method == 'POST':
        form = SessionForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"✅ Session on {obj.date} created.")
            return redirect('academics:admin_session_list')
    else:
        form = SessionForm()
    return render(request, 'academics/admin/session_form.html', {
        'form': form, 'title': 'Add Session', 'button_text': 'Create Session',
    })


@login_required
def admin_session_edit(request, pk):
    obj = get_object_or_404(Session, pk=pk)
    if not request.user.has_perm('academics.change_session'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_session_list')

    if request.method == 'POST':
        form = SessionForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Session updated.")
            return redirect('academics:admin_session_list')
    else:
        form = SessionForm(instance=obj)
    return render(request, 'academics/admin/session_form.html', {
        'form': form, 'session': obj, 'title': 'Edit Session', 'button_text': 'Update Session',
    })


@login_required
@require_POST
def admin_session_delete(request, pk):
    obj = get_object_or_404(Session, pk=pk)
    if not request.user.has_perm('academics.delete_session'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_session_list')
    obj.delete()
    messages.success(request, "🗑️ Session deleted.")
    return redirect('academics:admin_session_list')


# ============================================================
# PART 7 — EXCO ADMIN — MATERIALS
# ============================================================

@login_required
def admin_material_list(request):
    if not request.user.has_perm('academics.view_material'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    qs = Material.objects.select_related('course').order_by('-uploaded_at')
    course_filter = request.GET.get('course', '')
    if course_filter:
        qs = qs.filter(course_id=course_filter)

    page = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'academics/admin/material_list.html', {
        'materials': page, 'page_obj': page, 'is_paginated': page.has_other_pages(),
        'courses': Course.objects.filter(is_active=True),
        'course_filter': course_filter,
    })


@login_required
def admin_material_create(request):
    if not request.user.has_perm('academics.add_material'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_material_list')

    if request.method == 'POST':
        form = MaterialForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"✅ Material '{obj.title}' uploaded.")
            return redirect('academics:admin_material_list')
    else:
        form = MaterialForm()
    return render(request, 'academics/admin/material_form.html', {
        'form': form, 'title': 'Add Material', 'button_text': 'Upload Material',
    })


@login_required
def admin_material_edit(request, pk):
    obj = get_object_or_404(Material, pk=pk)
    if not request.user.has_perm('academics.change_material'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_material_list')

    if request.method == 'POST':
        form = MaterialForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Material updated.")
            return redirect('academics:admin_material_list')
    else:
        form = MaterialForm(instance=obj)
    return render(request, 'academics/admin/material_form.html', {
        'form': form, 'material': obj, 'title': 'Edit Material', 'button_text': 'Update Material',
    })


@login_required
@require_POST
def admin_material_delete(request, pk):
    obj = get_object_or_404(Material, pk=pk)
    if not request.user.has_perm('academics.delete_material'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_material_list')
    obj.delete()
    messages.success(request, "🗑️ Material deleted.")
    return redirect('academics:admin_material_list')


# ============================================================
# PART 8 — EXCO ADMIN — EVALUATIONS (EXAMS)
# ============================================================

@login_required
def admin_evaluation_list(request):
    if not request.user.has_perm('academics.view_evaluation'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    qs = Evaluation.objects.select_related('course').order_by('-date')
    course_filter = request.GET.get('course', '')
    if course_filter:
        qs = qs.filter(course_id=course_filter)

    page = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'academics/admin/evaluation_list.html', {
        'evaluations': page, 'page_obj': page, 'is_paginated': page.has_other_pages(),
        'courses': Course.objects.filter(is_active=True),
        'course_filter': course_filter,
    })


@login_required
def admin_evaluation_create(request):
    if not request.user.has_perm('academics.add_evaluation'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_evaluation_list')

    if request.method == 'POST':
        form = EvaluationForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"✅ Exam '{obj.title}' created.")
            return redirect('academics:admin_evaluation_list')
    else:
        form = EvaluationForm()
    return render(request, 'academics/admin/evaluation_form.html', {
        'form': form, 'title': 'Add Exam', 'button_text': 'Create Exam',
    })


@login_required
def admin_evaluation_edit(request, pk):
    obj = get_object_or_404(Evaluation, pk=pk)
    if not request.user.has_perm('academics.change_evaluation'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_evaluation_list')

    if request.method == 'POST':
        form = EvaluationForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Exam updated.")
            return redirect('academics:admin_evaluation_list')
    else:
        form = EvaluationForm(instance=obj)
    return render(request, 'academics/admin/evaluation_form.html', {
        'form': form, 'evaluation': obj, 'title': 'Edit Exam', 'button_text': 'Update Exam',
    })


@login_required
@require_POST
def admin_evaluation_delete(request, pk):
    obj = get_object_or_404(Evaluation, pk=pk)
    if not request.user.has_perm('academics.delete_evaluation'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_evaluation_list')
    obj.delete()
    messages.success(request, "🗑️ Exam deleted.")
    return redirect('academics:admin_evaluation_list')


@login_required
def admin_evaluation_upload_results(request, pk):
    """Upload results for an evaluation via Excel."""
    evaluation = get_object_or_404(Evaluation, pk=pk)
    if not request.user.has_perm('academics.add_result'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_evaluation_list')

    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            messages.error(request, "Please select a file.")
        else:
            try:
                wb = openpyxl.load_workbook(excel_file)
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))
                created = 0
                errors = []
                for idx, row in enumerate(rows[1:], start=2):
                    if not any(row):
                        continue
                    if len(row) < 3:
                        errors.append(f"Row {idx}: needs at least Name, Reg No, Marks")
                        continue
                    name = str(row[0]).strip() if row[0] else ''
                    reg_no = str(row[1]).strip() if len(row) > 1 and row[1] else ''
                    try:
                        marks = float(row[2]) if len(row) > 2 and row[2] is not None else 0
                    except (ValueError, TypeError):
                        marks = 0
                    grade = str(row[3]).strip() if len(row) > 3 and row[3] else ''
                    remarks = str(row[4]).strip() if len(row) > 4 and row[4] else ''
                    Result.objects.create(
                        evaluation=evaluation,
                        student_name=name,
                        registration_number=reg_no,
                        marks_obtained=marks,
                        grade=grade,
                        remarks=remarks,
                    )
                    created += 1
                messages.success(request, f"✅ {created} result(s) imported.")
                if errors:
                    for e in errors[:5]:
                        messages.warning(request, e)
                return redirect('academics:admin_evaluation_list')
            except Exception as e:
                messages.error(request, f"Error reading file: {e}")

    return render(request, 'academics/admin/evaluation_upload.html', {
        'evaluation': evaluation,
    })


# ============================================================
# PART 9 — EXCO ADMIN — RESULTS
# ============================================================

@login_required
def admin_result_list(request):
    if not request.user.has_perm('academics.view_result'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    # ---- Bulk action ----
    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if not ids:
            messages.warning(request, "No results selected.")
            return redirect('academics:admin_result_list')

        if action == 'delete' and request.user.has_perm('academics.delete_result'):
            count = Result.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} result(s) deleted.")
        else:
            messages.error(request, "Invalid action or permission denied.")
        return redirect('academics:admin_result_list')

    # ---- Filters ----
    qs = Result.objects.select_related('evaluation__course').order_by('student_name')
    evaluation_filter = request.GET.get('evaluation', '')
    query = request.GET.get('q', '')
    if evaluation_filter:
        qs = qs.filter(evaluation_id=evaluation_filter)
    if query:
        qs = qs.filter(Q(student_name__icontains=query) | Q(registration_number__icontains=query))

    page = Paginator(qs, 30).get_page(request.GET.get('page'))
    return render(request, 'academics/admin/result_list.html', {
        'results': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'evaluations': Evaluation.objects.select_related('course').order_by('-date')[:100],
        'evaluation_filter': evaluation_filter,
        'query': query,
    })



@login_required
@require_POST
def admin_result_delete(request, pk):
    obj = get_object_or_404(Result, pk=pk)
    if not request.user.has_perm('academics.delete_result'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_result_list')
    obj.delete()
    messages.success(request, "🗑️ Result deleted.")
    return redirect('academics:admin_result_list')


# ============================================================
# PART 10 — EXCO ADMIN — TIMETABLE
# ============================================================

@login_required
def admin_timetable_list(request):
    if not request.user.has_perm('academics.view_timetableentry'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    qs = TimetableEntry.objects.all().order_by('entry_type', 'level', 'day', 'time_start')
    type_filter = request.GET.get('type', '')
    level_filter = request.GET.get('level', '')
    if type_filter:
        qs = qs.filter(entry_type=type_filter)
    if level_filter:
        qs = qs.filter(level=level_filter)

    page = Paginator(qs, 40).get_page(request.GET.get('page'))
    return render(request, 'academics/admin/timetable_list.html', {
        'entries': page, 'page_obj': page, 'is_paginated': page.has_other_pages(),
        'type_filter': type_filter, 'level_filter': level_filter,
    })


@login_required
def admin_timetable_create(request):
    if not request.user.has_perm('academics.add_timetableentry'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_timetable_list')

    if request.method == 'POST':
        form = TimetableForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"✅ Timetable entry '{obj.course_name}' created.")
            return redirect('academics:admin_timetable_list')
    else:
        form = TimetableForm()
    return render(request, 'academics/admin/timetable_form.html', {
        'form': form, 'title': 'Add Timetable Entry', 'button_text': 'Create Entry',
    })


@login_required
def admin_timetable_edit(request, pk):
    obj = get_object_or_404(TimetableEntry, pk=pk)
    if not request.user.has_perm('academics.change_timetableentry'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_timetable_list')

    if request.method == 'POST':
        form = TimetableForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Timetable entry updated.")
            return redirect('academics:admin_timetable_list')
    else:
        form = TimetableForm(instance=obj)
    return render(request, 'academics/admin/timetable_form.html', {
        'form': form, 'entry': obj, 'title': 'Edit Timetable Entry', 'button_text': 'Update Entry',
    })


@login_required
@require_POST
def admin_timetable_delete(request, pk):
    obj = get_object_or_404(TimetableEntry, pk=pk)
    if not request.user.has_perm('academics.delete_timetableentry'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_timetable_list')
    obj.delete()
    messages.success(request, "🗑️ Timetable entry deleted.")
    return redirect('academics:admin_timetable_list')


# ============================================================
# PART 11 — EXCO ADMIN — ISLAMIYYA COURSES
# ============================================================

@login_required
def admin_islamiyya_course_list(request):
    if not request.user.has_perm('academics.view_islamiyyacourse'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    qs = IslamiyyaCourse.objects.all().order_by('name')
    page = Paginator(qs, 30).get_page(request.GET.get('page'))
    return render(request, 'academics/admin/islamiyya_course_list.html', {
        'courses': page, 'page_obj': page, 'is_paginated': page.has_other_pages(),
    })


@login_required
def admin_islamiyya_course_create(request):
    if not request.user.has_perm('academics.add_islamiyyacourse'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_islamiyya_course_list')

    if request.method == 'POST':
        form = IslamiyyaCourseForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"✅ Islamiyya course '{obj.name}' created.")
            return redirect('academics:admin_islamiyya_course_list')
    else:
        form = IslamiyyaCourseForm()
    return render(request, 'academics/admin/islamiyya_course_form.html', {
        'form': form, 'title': 'Add Islamiyya Course', 'button_text': 'Create',
    })


@login_required
def admin_islamiyya_course_edit(request, pk):
    obj = get_object_or_404(IslamiyyaCourse, pk=pk)
    if not request.user.has_perm('academics.change_islamiyyacourse'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_islamiyya_course_list')

    if request.method == 'POST':
        form = IslamiyyaCourseForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Islamiyya course updated.")
            return redirect('academics:admin_islamiyya_course_list')
    else:
        form = IslamiyyaCourseForm(instance=obj)
    return render(request, 'academics/admin/islamiyya_course_form.html', {
        'form': form, 'course': obj, 'title': 'Edit Islamiyya Course', 'button_text': 'Update',
    })


@login_required
@require_POST
def admin_islamiyya_course_delete(request, pk):
    obj = get_object_or_404(IslamiyyaCourse, pk=pk)
    if not request.user.has_perm('academics.delete_islamiyyacourse'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_islamiyya_course_list')
    obj.delete()
    messages.success(request, "🗑️ Islamiyya course deleted.")
    return redirect('academics:admin_islamiyya_course_list')


# ============================================================
# PART 12 — EXCO ADMIN — ISLAMIYYA SETTINGS
# ============================================================

@login_required
def admin_islamiyya_settings_list(request):
    if not request.user.has_perm('academics.view_islamiyyasettings'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    settings_qs = (
        IslamiyyaSettings.objects
        .select_related('account')
        .annotate(
            paid_count_ann=Count('registrations', filter=Q(registrations__payment_status='paid')),
            pending_count_ann=Count('registrations', filter=Q(registrations__payment_status='pending')),
        )
        .order_by('-academic_session')
    )
    return render(request, 'academics/admin/islamiyya_settings_list.html', {
        'settings_list': settings_qs,
    })


@login_required
def admin_islamiyya_settings_create(request):
    if not request.user.has_perm('academics.add_islamiyyasettings'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_islamiyya_settings_list')

    if request.method == 'POST':
        form = IslamiyyaSettingsForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"✅ Session '{obj.academic_session}' created.")
            return redirect('academics:admin_islamiyya_settings_list')
    else:
        form = IslamiyyaSettingsForm()
    return render(request, 'academics/admin/islamiyya_settings_form.html', {
        'form': form, 'title': 'Add Islamiyya Session', 'button_text': 'Create Session',
    })


@login_required
def admin_islamiyya_settings_edit(request, pk):
    obj = get_object_or_404(IslamiyyaSettings, pk=pk)
    if not request.user.has_perm('academics.change_islamiyyasettings'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_islamiyya_settings_list')

    if request.method == 'POST':
        form = IslamiyyaSettingsForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Islamiyya session updated.")
            return redirect('academics:admin_islamiyya_settings_list')
    else:
        form = IslamiyyaSettingsForm(instance=obj)
    return render(request, 'academics/admin/islamiyya_settings_form.html', {
        'form': form, 'settings_obj': obj,
        'title': f'Edit {obj.academic_session}', 'button_text': 'Save Changes',
    })


@login_required
@require_POST
def admin_islamiyya_settings_delete(request, pk):
    obj = get_object_or_404(IslamiyyaSettings, pk=pk)
    if not request.user.has_perm('academics.delete_islamiyyasettings'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_islamiyya_settings_list')
    session = obj.academic_session
    obj.delete()
    messages.success(request, f"🗑️ Session '{session}' deleted.")
    return redirect('academics:admin_islamiyya_settings_list')


@login_required
@require_POST
def admin_islamiyya_settings_activate(request, pk):
    obj = get_object_or_404(IslamiyyaSettings, pk=pk)
    if not request.user.has_perm('academics.change_islamiyyasettings'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_islamiyya_settings_list')
    obj.is_active = True
    obj.save()
    messages.success(request, f"✅ '{obj.academic_session}' is now the active session.")
    return redirect('academics:admin_islamiyya_settings_list')


@login_required
@require_POST
def admin_islamiyya_settings_toggle_open(request, pk):
    """Flip the is_open flag quickly."""
    obj = get_object_or_404(IslamiyyaSettings, pk=pk)
    if not request.user.has_perm('academics.change_islamiyyasettings'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_islamiyya_settings_list')
    obj.is_open = not obj.is_open
    obj.save(update_fields=['is_open'])
    state = 'opened' if obj.is_open else 'closed'
    messages.success(request, f"✅ Registration for '{obj.academic_session}' {state}.")
    return redirect('academics:admin_islamiyya_settings_list')


# ============================================================
# PART 13 — EXCO ADMIN — ISLAMIYYA REGISTRATIONS
# ============================================================

@login_required
def admin_islamiyya_registration_list(request):
    if not request.user.has_perm('academics.view_islamiyyaregistration'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    session_filter = request.GET.get('session', '')
    level_filter = request.GET.get('level', '')

    qs = IslamiyyaRegistration.objects.select_related('session_settings').order_by('-submitted_at')
    if query:
        qs = qs.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(application_id__icontains=query) |
            Q(registration_number__icontains=query) |
            Q(phone__icontains=query)
        )
    if status_filter:
        qs = qs.filter(payment_status=status_filter)
    if session_filter:
        qs = qs.filter(session_settings_id=session_filter)
    if level_filter:
        qs = qs.filter(level=level_filter)

    page = Paginator(qs, 30).get_page(request.GET.get('page'))
    return render(request, 'academics/admin/islamiyya_registration_list.html', {
        'registrations': page, 'page_obj': page, 'is_paginated': page.has_other_pages(),
        'query': query, 'status_filter': status_filter,
        'session_filter': session_filter, 'level_filter': level_filter,
        'sessions': IslamiyyaSettings.objects.all().order_by('-academic_session'),
    })


@login_required
def admin_islamiyya_registration_detail(request, pk):
    reg = get_object_or_404(IslamiyyaRegistration, pk=pk)
    if not request.user.has_perm('academics.view_islamiyyaregistration'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    return render(request, 'academics/admin/islamiyya_registration_detail.html', {
        'registration': reg,
        'attendance_records': reg.attendance_records.select_related('session')[:20],
    })


@login_required
def admin_islamiyya_registration_edit(request, pk):
    reg = get_object_or_404(IslamiyyaRegistration, pk=pk)
    if not request.user.has_perm('academics.change_islamiyyaregistration'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_islamiyya_registration_list')

    if request.method == 'POST':
        form = IslamiyyaRegistrationAdminForm(request.POST, request.FILES, instance=reg)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ {reg.name}'s registration updated.")
            return redirect('academics:admin_islamiyya_registration_detail', pk=reg.pk)
    else:
        form = IslamiyyaRegistrationAdminForm(instance=reg)
    return render(request, 'academics/admin/islamiyya_registration_form.html', {
        'form': form, 'registration': reg,
        'title': f'Edit {reg.name}', 'button_text': 'Save Changes',
    })


@login_required
@require_POST
def admin_islamiyya_registration_delete(request, pk):
    reg = get_object_or_404(IslamiyyaRegistration, pk=pk)
    if not request.user.has_perm('academics.delete_islamiyyaregistration'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_islamiyya_registration_list')
    name = reg.name
    reg.delete()
    messages.success(request, f"🗑️ Registration for {name} deleted.")
    return redirect('academics:admin_islamiyya_registration_list')


@login_required
@require_POST
def admin_islamiyya_registration_mark_paid(request, pk):
    """Mark registration as paid (manual / mosque / cash)."""
    reg = get_object_or_404(IslamiyyaRegistration, pk=pk)
    if not request.user.has_perm('academics.change_islamiyyaregistration'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_islamiyya_registration_detail', pk=pk)

    if reg.is_paid:
        messages.info(request, "This registration is already marked as paid.")
        return redirect('academics:admin_islamiyya_registration_detail', pk=pk)

    fee = reg.session_settings.registration_fee if reg.session_settings else 0
    _complete_islamiyya_payment(
        reg,
        amount=fee,
        method='manual',
        reference=f'MANUAL-{timezone.now().strftime("%Y%m%d%H%M%S")}-{reg.id}',
        verified_by=request.user,
    )
    messages.success(request, f"✅ {reg.name} marked as paid. WhatsApp link unlocked.")
    return redirect('academics:admin_islamiyya_registration_detail', pk=pk)


@login_required
@require_POST
def admin_islamiyya_registration_waive(request, pk):
    """Waive the fee — student admitted without payment."""
    reg = get_object_or_404(IslamiyyaRegistration, pk=pk)
    if not request.user.has_perm('academics.change_islamiyyaregistration'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_islamiyya_registration_detail', pk=pk)

    if reg.payment_status != 'pending':
        messages.info(request, "Only pending registrations can be waived.")
        return redirect('academics:admin_islamiyya_registration_detail', pk=pk)

    note = request.POST.get('note', 'Fee waived by EXCO')
    reg.mark_waived(by_user=request.user, note=note)
    messages.success(request, f"✅ Fee waived for {reg.name}.")
    return redirect('academics:admin_islamiyya_registration_detail', pk=pk)


@login_required
@require_POST
def admin_islamiyya_registration_refund(request, pk):
    """Mark as refunded (physical refund handled at mosque)."""
    reg = get_object_or_404(IslamiyyaRegistration, pk=pk)
    if not request.user.has_perm('academics.change_islamiyyaregistration'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_islamiyya_registration_detail', pk=pk)

    if reg.payment_status != 'paid':
        messages.info(request, "Only paid registrations can be refunded.")
        return redirect('academics:admin_islamiyya_registration_detail', pk=pk)

    note = request.POST.get('note', 'Refunded at mosque')
    reg.mark_refunded(by_user=request.user, note=note)
    messages.success(request, f"↺ {reg.name}'s registration marked as refunded.")
    return redirect('academics:admin_islamiyya_registration_detail', pk=pk)


@login_required
@require_POST
def admin_islamiyya_registration_issue_certificate(request, pk):
    """Issue a completion certificate."""
    reg = get_object_or_404(IslamiyyaRegistration, pk=pk)
    if not request.user.has_perm('academics.change_islamiyyaregistration'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_islamiyya_registration_detail', pk=pk)

    if not reg.is_paid:
        messages.error(request, "Cannot issue certificate — payment not verified.")
        return redirect('academics:admin_islamiyya_registration_detail', pk=pk)

    if reg.certificate_issued:
        messages.info(request, f"Certificate already issued: {reg.certificate_number}")
        return redirect('academics:admin_islamiyya_registration_detail', pk=pk)

    cert_no = reg.issue_certificate(by_user=request.user)
    messages.success(request, f"🎓 Certificate {cert_no} issued for {reg.name}.")
    return redirect('academics:admin_islamiyya_registration_detail', pk=pk)



@login_required
def admin_islamiyya_verification_queue(request):
    """Only pending registrations — the workflow page for EXCO."""
    if not request.user.has_perm('academics.change_islamiyyaregistration'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    qs = IslamiyyaRegistration.objects.filter(
        payment_status='pending'
    ).select_related('session_settings').order_by('-submitted_at')

    session_filter = request.GET.get('session', '')
    if session_filter:
        qs = qs.filter(session_settings_id=session_filter)

    query = request.GET.get('q', '')
    if query:
        qs = qs.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(registration_number__icontains=query) |
            Q(application_id__icontains=query)
        )

    page = Paginator(qs, 50).get_page(request.GET.get('page'))
    return render(request, 'academics/admin/islamiyya_verification_queue.html', {
        'registrations': page, 'page_obj': page, 'is_paginated': page.has_other_pages(),
        'query': query, 'session_filter': session_filter,
        'sessions': IslamiyyaSettings.objects.all().order_by('-academic_session'),
    })


# ---------- ISLAMIYYA BULK ACTIONS ----------

@login_required
@require_POST
def admin_islamiyya_bulk_mark_paid(request):
    if not request.user.has_perm('academics.change_islamiyyaregistration'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_islamiyya_verification_queue')

    ids = request.POST.getlist('selected_ids')
    if not ids:
        messages.warning(request, "No registrations selected.")
        return redirect('academics:admin_islamiyya_verification_queue')

    method = request.POST.get('method', 'manual')
    count = 0
    for reg in IslamiyyaRegistration.objects.filter(id__in=ids, payment_status='pending'):
        fee = reg.session_settings.registration_fee if reg.session_settings else 0
        _complete_islamiyya_payment(
            reg,
            amount=fee,
            method=method,
            reference=f'MANUAL-{timezone.now().strftime("%Y%m%d%H%M%S")}-{reg.id}',
            verified_by=request.user,
        )
        count += 1

    messages.success(request, f"✅ {count} registration(s) marked as paid ({method}).")
    return redirect('academics:admin_islamiyya_verification_queue')


@login_required
@require_POST
def admin_islamiyya_bulk_waive(request):
    if not request.user.has_perm('academics.change_islamiyyaregistration'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_islamiyya_verification_queue')

    ids = request.POST.getlist('selected_ids')
    note = request.POST.get('note', 'Bulk waiver')

    count = 0
    for reg in IslamiyyaRegistration.objects.filter(id__in=ids, payment_status='pending'):
        reg.mark_waived(by_user=request.user, note=note)
        count += 1

    messages.success(request, f"✅ {count} registration(s) fee waived.")
    return redirect('academics:admin_islamiyya_verification_queue')


@login_required
@require_POST
def admin_islamiyya_bulk_refund(request):
    if not request.user.has_perm('academics.change_islamiyyaregistration'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_islamiyya_registration_list')

    ids = request.POST.getlist('selected_ids')
    note = request.POST.get('note', 'Refunded at mosque')

    count = 0
    for reg in IslamiyyaRegistration.objects.filter(id__in=ids, payment_status='paid'):
        reg.mark_refunded(by_user=request.user, note=note)
        count += 1

    messages.success(request, f"↺ {count} registration(s) marked refunded.")
    return redirect('academics:admin_islamiyya_registration_list')


@login_required
@require_POST
def admin_islamiyya_bulk_issue_certificate(request):
    if not request.user.has_perm('academics.change_islamiyyaregistration'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_islamiyya_registration_list')

    ids = request.POST.getlist('selected_ids')
    count = 0
    for reg in IslamiyyaRegistration.objects.filter(id__in=ids, payment_status__in=['paid', 'waived'],
                                                     certificate_issued=False):
        reg.issue_certificate(by_user=request.user)
        count += 1

    messages.success(request, f"🎓 {count} certificate(s) issued.")
    return redirect('academics:admin_islamiyya_registration_list')


@login_required
@require_POST
def admin_islamiyya_send_whatsapp_link(request, pk):
    """Email the student their WhatsApp link (or resend)."""
    reg = get_object_or_404(IslamiyyaRegistration, pk=pk)
    if not request.user.has_perm('academics.change_islamiyyaregistration'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_islamiyya_registration_list')

    if not reg.is_paid or not reg.whatsapp_link:
        messages.error(request, "Cannot send link — payment not verified or no link set.")
        return redirect('academics:admin_islamiyya_registration_detail', pk=pk)

    try:
        send_templated_email(
            subject="Welcome to NAMETS Islamiyya — your WhatsApp link",
            recipients=[reg.email],
            template_name='emails/islamiyya_whatsapp_link.html',
            context={
                'name': reg.name,
                'app_id': reg.application_id,
                'whatsapp_link': reg.whatsapp_link,
            },
        )
        messages.success(request, f"✅ WhatsApp link sent to {reg.email}.")
    except Exception as e:
        messages.error(request, f"Failed to send: {e}")

    return redirect('academics:admin_islamiyya_registration_detail', pk=pk)


# ---------- ISLAMIYYA EXPORT ----------

@login_required
def admin_islamiyya_registration_export(request):
    if not request.user.has_perm('academics.view_islamiyyaregistration'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    qs = IslamiyyaRegistration.objects.select_related('session_settings').order_by('-submitted_at')
    session_filter = request.GET.get('session', '')
    status_filter = request.GET.get('status', '')
    if session_filter:
        qs = qs.filter(session_settings_id=session_filter)
    if status_filter:
        qs = qs.filter(payment_status=status_filter)

    spec = ImportSpec()
    spec.key = 'islamiyya_export'
    spec.label = 'Islamiyya Registrations'
    spec.columns = [
        ColumnSpec('application_id', 'Application ID'),
        ColumnSpec('session', 'Session'),
        ColumnSpec('name', 'Name'),
        ColumnSpec('registration_number', 'Reg No'),
        ColumnSpec('email', 'Email'),
        ColumnSpec('phone', 'Phone'),
        ColumnSpec('department', 'Department'),
        ColumnSpec('level', 'Level'),
        ColumnSpec('payment_status', 'Payment Status'),
        ColumnSpec('payment_method', 'Method'),
        ColumnSpec('amount_paid', 'Amount Paid'),
        ColumnSpec('paid_at', 'Paid At'),
        ColumnSpec('certificate', 'Certificate'),
        ColumnSpec('submitted_at', 'Submitted At'),
    ]

    def row(reg):
        return {
            'application_id': reg.application_id,
            'session': reg.session_settings.academic_session if reg.session_settings else '',
            'name': reg.name,
            'registration_number': reg.registration_number,
            'email': reg.email,
            'phone': reg.phone,
            'department': reg.department or '',
            'level': reg.get_level_display(),
            'payment_status': reg.get_payment_status_display(),
            'payment_method': reg.get_payment_method_display() if reg.payment_method else '',
            'amount_paid': float(reg.amount_paid or 0),
            'paid_at': reg.paid_at.strftime('%Y-%m-%d %H:%M') if reg.paid_at else '',
            'certificate': reg.certificate_number or '',
            'submitted_at': reg.submitted_at.strftime('%Y-%m-%d %H:%M'),
        }

    spec.export_queryset = lambda: qs
    spec.row_from_instance = row
    return build_export_xlsx(spec)


# ---------- ISLAMIYYA ANALYTICS ----------

@login_required
def admin_islamiyya_analytics(request):
    if not request.user.has_perm('academics.view_islamiyyaregistration'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    session_filter = request.GET.get('session', '')
    qs = IslamiyyaRegistration.objects.all()
    if session_filter:
        qs = qs.filter(session_settings_id=session_filter)

    total = qs.count()
    paid = qs.filter(payment_status='paid').count()
    pending = qs.filter(payment_status='pending').count()
    refunded = qs.filter(payment_status='refunded').count()
    waived = qs.filter(payment_status='waived').count()

    total_collected = qs.filter(payment_status='paid').aggregate(t=Sum('amount_paid'))['t'] or 0

    # By level
    by_level = qs.values('level').annotate(count=Count('id')).order_by()

    # By course
    by_course = (
        IslamiyyaCourse.objects
        .filter(islamiyyaregistration__in=qs)
        .annotate(count=Count('islamiyyaregistration'))
        .order_by('-count')[:10]
    )

    # Daily registrations (last 30 days)
    since = timezone.now() - timedelta(days=30)
    daily = (
        qs.filter(submitted_at__gte=since)
        .extra(select={'day': 'date(submitted_at)'})
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    return render(request, 'academics/admin/islamiyya_analytics.html', {
        'total': total, 'paid': paid, 'pending': pending,
        'refunded': refunded, 'waived': waived,
        'total_collected': total_collected,
        'by_level': by_level,
        'by_course': by_course,
        'daily': list(daily),
        'sessions': IslamiyyaSettings.objects.all().order_by('-academic_session'),
        'session_filter': session_filter,
    })


# ============================================================
# PART 14 — EXCO ADMIN — RESOURCE SUBMISSIONS
# ============================================================

@login_required
def admin_resource_list(request):
    if not request.user.has_perm('academics.view_userresourcesubmission'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    qs = UserResourceSubmission.objects.all().order_by('-submitted_at')
    status_filter = request.GET.get('status', '')
    query = request.GET.get('q', '')
    if status_filter:
        qs = qs.filter(status=status_filter)
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(submitted_by__icontains=query) | Q(email__icontains=query))

    page = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'academics/admin/resource_list.html', {
        'resources': page, 'page_obj': page, 'is_paginated': page.has_other_pages(),
        'status_filter': status_filter, 'query': query,
        'pending_count': UserResourceSubmission.objects.filter(status='pending').count(),
    })


@login_required
def admin_resource_review(request, pk):
    """Full review page — view, download, approve or reject."""
    resource = get_object_or_404(UserResourceSubmission, pk=pk)
    if not request.user.has_perm('academics.change_userresourcesubmission'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_resource_list')

    return render(request, 'academics/admin/resource_review.html', {
        'resource': resource,
    })


@login_required
@require_POST
def admin_resource_approve(request, pk):
    resource = get_object_or_404(UserResourceSubmission, pk=pk)
    if not request.user.has_perm('academics.change_userresourcesubmission'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_resource_list')

    resource.status = 'approved'
    resource.reviewed_at = timezone.now()
    resource.reviewed_by = request.user
    resource.review_note = request.POST.get('note', '')
    resource.save()

    if resource.email and not resource.email_sent:
        try:
            send_templated_email(
                subject="Your NAMETS resource has been approved",
                recipients=[resource.email],
                template_name='emails/resource_approved.html',
                context={
                    'name': resource.submitted_by or 'User',
                    'title': resource.title,
                    'resources_url': getattr(settings, 'SITE_URL', '') + '/academics/resources/',
                },
            )
            resource.email_sent = True
            resource.save(update_fields=['email_sent'])
        except Exception:
            pass

    messages.success(request, f"✅ Resource '{resource.title}' approved.")
    return redirect('academics:admin_resource_list')


@login_required
@require_POST
def admin_resource_reject(request, pk):
    resource = get_object_or_404(UserResourceSubmission, pk=pk)
    if not request.user.has_perm('academics.change_userresourcesubmission'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_resource_list')

    resource.status = 'rejected'
    resource.reviewed_at = timezone.now()
    resource.reviewed_by = request.user
    resource.review_note = request.POST.get('note', '')
    resource.save()

    messages.success(request, f"❌ Resource '{resource.title}' rejected.")
    return redirect('academics:admin_resource_list')


@login_required
@require_POST
def admin_resource_delete(request, pk):
    resource = get_object_or_404(UserResourceSubmission, pk=pk)
    if not request.user.has_perm('academics.delete_userresourcesubmission'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_resource_list')
    title = resource.title
    resource.delete()
    messages.success(request, f"🗑️ Resource '{title}' deleted.")
    return redirect('academics:admin_resource_list')


# ============================================================
# PART 15 — EXCO ADMIN — TUTOR EVALUATIONS (READ-ONLY)
# ============================================================

@login_required
def admin_tutor_evaluation_list(request):
    if not request.user.has_perm('academics.view_tutorevaluation'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    qs = TutorEvaluation.objects.select_related('course', 'tutor').order_by('-submitted_at')
    course_filter = request.GET.get('course', '')
    tutor_filter = request.GET.get('tutor', '')
    rating_filter = request.GET.get('rating', '')
    if course_filter:
        qs = qs.filter(course_id=course_filter)
    if tutor_filter:
        qs = qs.filter(tutor_id=tutor_filter)
    if rating_filter:
        qs = qs.filter(rating=rating_filter)

    page = Paginator(qs, 30).get_page(request.GET.get('page'))
    return render(request, 'academics/admin/tutor_evaluation_list.html', {
        'evaluations': page, 'page_obj': page, 'is_paginated': page.has_other_pages(),
        'courses': Course.objects.filter(is_active=True),
        'tutors': Tutor.objects.filter(is_active=True),
        'course_filter': course_filter, 'tutor_filter': tutor_filter,
        'rating_filter': rating_filter,
    })


@login_required
def admin_tutor_evaluation_export(request):
    if not request.user.has_perm('academics.view_tutorevaluation'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    qs = TutorEvaluation.objects.select_related('course', 'tutor').order_by('-submitted_at')
    course_filter = request.GET.get('course', '')
    if course_filter:
        qs = qs.filter(course_id=course_filter)

    spec = ImportSpec()
    spec.key = 'tutor_evaluation_export'
    spec.label = 'Tutor Evaluations'
    spec.columns = [
        ColumnSpec('course', 'Course'),
        ColumnSpec('tutor', 'Tutor'),
        ColumnSpec('student_name', 'Student'),
        ColumnSpec('rating', 'Rating'),
        ColumnSpec('comments', 'Comments'),
        ColumnSpec('submitted_at', 'Submitted At'),
    ]

    def row(ev):
        return {
            'course': str(ev.course),
            'tutor': ev.tutor.name,
            'student_name': ev.student_name or 'Anonymous',
            'rating': ev.rating,
            'comments': ev.comments,
            'submitted_at': ev.submitted_at.strftime('%Y-%m-%d %H:%M'),
        }

    spec.export_queryset = lambda: qs
    spec.row_from_instance = row
    return build_export_xlsx(spec)


# ============================================================
# PART 16 — EXCO ADMIN — COMPETITION RESULTS
# ============================================================

@login_required
def admin_competition_list(request):
    if not request.user.has_perm('academics.view_competitionresult'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    qs = CompetitionResult.objects.all().order_by('event_name', 'category', 'order', 'position')
    event_filter = request.GET.get('event', '')
    if event_filter:
        qs = qs.filter(event_name=event_filter)

    page = Paginator(qs, 40).get_page(request.GET.get('page'))
    return render(request, 'academics/admin/competition_list.html', {
        'results': page, 'page_obj': page, 'is_paginated': page.has_other_pages(),
        'events': CompetitionResult.objects.values_list('event_name', flat=True).distinct().order_by('event_name'),
        'event_filter': event_filter,
    })


@login_required
def admin_competition_create(request):
    if not request.user.has_perm('academics.add_competitionresult'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_competition_list')

    if request.method == 'POST':
        form = CompetitionResultForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"✅ Result added for {obj.participant_name}.")
            return redirect('academics:admin_competition_list')
    else:
        form = CompetitionResultForm()
    return render(request, 'academics/admin/competition_form.html', {
        'form': form, 'title': 'Add Competition Result', 'button_text': 'Create',
    })


@login_required
def admin_competition_edit(request, pk):
    obj = get_object_or_404(CompetitionResult, pk=pk)
    if not request.user.has_perm('academics.change_competitionresult'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_competition_list')

    if request.method == 'POST':
        form = CompetitionResultForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Result updated.")
            return redirect('academics:admin_competition_list')
    else:
        form = CompetitionResultForm(instance=obj)
    return render(request, 'academics/admin/competition_form.html', {
        'form': form, 'result': obj, 'title': 'Edit Result', 'button_text': 'Update',
    })


@login_required
@require_POST
def admin_competition_delete(request, pk):
    obj = get_object_or_404(CompetitionResult, pk=pk)
    if not request.user.has_perm('academics.delete_competitionresult'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_competition_list')
    obj.delete()
    messages.success(request, "🗑️ Result deleted.")
    return redirect('academics:admin_competition_list')


@login_required
def admin_competition_upload(request):
    if not request.user.has_perm('academics.add_competitionresult'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_competition_list')

    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            messages.error(request, "Please select a file.")
        else:
            try:
                wb = openpyxl.load_workbook(excel_file)
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))
                created = 0
                for row in rows[1:]:
                    if not any(row):
                        continue
                    try:
                        CompetitionResult.objects.create(
                            event_name=str(row[0]).strip() if row[0] else '',
                            category=str(row[1]).strip() if len(row) > 1 and row[1] else '',
                            position=str(row[2]).strip() if len(row) > 2 and row[2] else 'participant',
                            participant_name=str(row[3]).strip() if len(row) > 3 and row[3] else '',
                            department=str(row[4]).strip() if len(row) > 4 and row[4] else '',
                            points=float(row[5]) if len(row) > 5 and row[5] else None,
                            year=str(row[6]).strip() if len(row) > 6 and row[6] else '',
                            order=int(row[7]) if len(row) > 7 and row[7] else 0,
                            is_active=True,
                        )
                        created += 1
                    except Exception:
                        continue
                messages.success(request, f"✅ {created} result(s) imported.")
                return redirect('academics:admin_competition_list')
            except Exception as e:
                messages.error(request, f"Error reading file: {e}")

    return render(request, 'academics/admin/competition_upload.html')


# ============================================================
# PART 17 — EXCO ADMIN — ATTENDANCE
# ============================================================
@login_required
def admin_attendance_list(request):
    if not request.user.has_perm('academics.view_attendancesession'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    # ---- Base queryset (filtered) ----
    qs = (
        AttendanceSession.objects
        .select_related('course', 'taken_by', 'islamiyya_settings')
        .order_by('-date')
    )
    type_filter = request.GET.get('type', '')
    if type_filter:
        qs = qs.filter(session_type=type_filter)

    # ---- Summary stats (always unfiltered so tab counts stay accurate) ----
    all_sessions = AttendanceSession.objects.all()
    summary = {
        'total_sessions': all_sessions.count(),
        'tutorials':      all_sessions.filter(session_type='tutorial').count(),
        'islamiyya':      all_sessions.filter(session_type='islamiyyah').count(),
        'exco':           all_sessions.filter(session_type='exco_meeting').count(),
        'events':         all_sessions.filter(session_type='event').count(),
    }

    # ---- Paginate the filtered queryset ----
    page = Paginator(qs, 30).get_page(request.GET.get('page'))

    return render(request, 'academics/admin/attendance_list.html', {
        'sessions': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'type_filter': type_filter,
        'summary': summary,
    })

@login_required
def admin_attendance_create(request):
    if not request.user.has_perm('academics.add_attendancesession'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_attendance_list')

    if request.method == 'POST':
        form = AttendanceSessionForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.taken_by = request.user
            obj.save()
            messages.success(request, f"✅ Attendance session created. Add attendees next.")
            return redirect('academics:admin_attendance_edit', pk=obj.pk)
    else:
        form = AttendanceSessionForm()
    return render(request, 'academics/admin/attendance_form.html', {
        'form': form, 'title': 'New Attendance Session', 'button_text': 'Create',
    })


@login_required
def admin_attendance_edit(request, pk):
    """Edit session + mark attendance. Auto-populates candidates based on session type."""
    session = get_object_or_404(AttendanceSession, pk=pk)
    if not request.user.has_perm('academics.change_attendancesession'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_attendance_list')

    # ---------- Determine mode + build candidate list ----------
    mode = session.session_type
    candidates = []  # list of dicts: {kind, obj_id, name, meta}

    if mode == 'islamiyyah':
        settings_obj = session.islamiyya_settings
        if settings_obj:
            # 1. Paid / waived students
            regs = IslamiyyaRegistration.objects.filter(
                session_settings=settings_obj,
                payment_status__in=['paid', 'waived'],
            ).order_by('name')
            for r in regs:
                candidates.append({
                    'kind': 'islamiyya_registration',
                    'obj_id': r.id,
                    'name': r.name,
                    'meta': f"Student · {r.get_level_display()} · {r.application_id}",
                })
            # 2. Islamiyya tutors
            tutors = Tutor.objects.filter(
                is_active=True,
                courses__course_type='islamiyya',
            ).distinct().order_by('name')
            for t in tutors:
                candidates.append({
                    'kind': 'tutor',
                    'obj_id': t.id,
                    'name': t.name,
                    'meta': f"Tutor · {t.email or 'no email'}",
                })

    elif mode == 'exco_meeting':
        # All users with active OfficeAssignment
        from accounts.models import OfficeAssignment
        assignments = (
            OfficeAssignment.objects
            .filter(is_active=True)
            .select_related('user', 'office')
            .order_by('office__name', 'user__first_name')
        )
        seen_users = set()
        for a in assignments:
            if a.user_id in seen_users:
                continue
            seen_users.add(a.user_id)
            candidates.append({
                'kind': 'user',
                'obj_id': a.user_id,
                'name': a.user.get_full_name() or a.user.username,
                'meta': f"{a.display_label or a.office.name}",
            })

    elif mode == 'tutorial' and session.course:
        # All EXCO members can be tutorial attendees if desired
        # OR you can use a specific enrollment list. For now, EXCO.
        from accounts.models import OfficeAssignment
        assignments = (
            OfficeAssignment.objects
            .filter(is_active=True)
            .select_related('user', 'office')
        )
        seen_users = set()
        for a in assignments:
            if a.user_id in seen_users:
                continue
            seen_users.add(a.user_id)
            candidates.append({
                'kind': 'user',
                'obj_id': a.user_id,
                'name': a.user.get_full_name() or a.user.username,
                'meta': a.display_label or a.office.name,
            })

    # 'event' mode: no auto-population — manual names only

    # ---------- POST: save attendance ----------
    if request.method == 'POST':
        session.records.all().delete()
        present_ids = set(request.POST.getlist('present_ids'))
        manual_names = request.POST.get('manual_names', '').strip()

        def is_present(kind, obj_id):
            return f"{kind}:{obj_id}" in present_ids

        # Save known candidates
        for c in candidates:
            kind = c['kind']
            obj_id = c['obj_id']
            if kind == 'user':
                AttendanceRecord.objects.create(
                    session=session,
                    user_id=obj_id,
                    present=is_present(kind, obj_id),
                )
            elif kind == 'islamiyya_registration':
                AttendanceRecord.objects.create(
                    session=session,
                    islamiyya_registration_id=obj_id,
                    present=is_present(kind, obj_id),
                )
            elif kind == 'tutor':
                # Store tutors as manual_name with role
                tutor = Tutor.objects.get(pk=obj_id)
                AttendanceRecord.objects.create(
                    session=session,
                    manual_name=tutor.name,
                    manual_role='Tutor',
                    present=is_present(kind, obj_id),
                )

        # Save manual names (one per line: "Name" or "Name — Role")
        for line in manual_names.splitlines():
            line = line.strip()
            if not line:
                continue
            if '—' in line or ' - ' in line:
                sep = '—' if '—' in line else ' - '
                name, role = line.split(sep, 1)
                name, role = name.strip(), role.strip()
            else:
                name, role = line, ''
            AttendanceRecord.objects.create(
                session=session,
                manual_name=name,
                manual_role=role,
                present=True,  # manually-added = present by default
            )

        messages.success(request, "✅ Attendance saved.")
        return redirect('academics:admin_attendance_list')

    # ---------- GET: build existing map ----------
    existing_present = set()
    existing_manual = []
    for r in session.records.all():
        if r.user:
            existing_present.add(f"user:{r.user_id}")
        elif r.islamiyya_registration:
            existing_present.add(f"islamiyya_registration:{r.islamiyya_registration_id}")
        elif r.manual_name:
            if r.manual_role == 'Tutor':
                # try to match tutor back
                existing_present.add(f"tutor:{r.id}")  # fallback
            else:
                existing_manual.append(f"{r.manual_name}" + (f" — {r.manual_role}" if r.manual_role else ""))

    return render(request, 'academics/admin/attendance_edit.html', {
        'session': session,
        'candidates': candidates,
        'existing_present': existing_present,
        'existing_manual': '\n'.join(existing_manual),
        'mode': mode,
    })



@login_required
def admin_attendance_report(request):
    """Analytics for attendance sessions — per-session + per-candidate stats."""
    if not request.user.has_perm('academics.view_attendancesession'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    session_type = request.GET.get('type', '')
    session_filter = request.GET.get('session', '')

    sessions = AttendanceSession.objects.select_related('course', 'islamiyya_settings').order_by('-date')
    if session_type:
        sessions = sessions.filter(session_type=session_type)
    if session_filter:
        sessions = sessions.filter(pk=session_filter)

    # Aggregate per-session stats
    session_stats = []
    for s in sessions[:200]:
        total = s.records.count()
        present = s.records.filter(present=True).count()
        session_stats.append({
            'session': s,
            'total': total,
            'present': present,
            'pct': (present / total * 100) if total else 0,
        })

    # Per-candidate stats (only for islamiyyah + user kinds)
    # Group by islamiyya_registration for islamiyyah sessions
    candidate_stats = []
    if session_type == 'islamiyyah' or not session_type:
        from django.db.models import Count, Q as QF
        regs = IslamiyyaRegistration.objects.filter(
            attendance_records__isnull=False
        ).annotate(
            total=Count('attendance_records'),
            present_count=Count('attendance_records', filter=QF(attendance_records__present=True)),
        ).order_by('name')
        for r in regs:
            candidate_stats.append({
                'name': r.name,
                'meta': r.get_level_display(),
                'total': r.total,
                'present': r.present_count,
                'pct': (r.present_count / r.total * 100) if r.total else 0,
            })

    return render(request, 'academics/admin/attendance_report.html', {
        'session_stats': session_stats,
        'candidate_stats': candidate_stats,
        'session_type': session_type,
        'session_filter': session_filter,
        'all_sessions': AttendanceSession.objects.order_by('-date')[:100],
    })


@login_required
@require_POST
def admin_attendance_delete(request, pk):
    session = get_object_or_404(AttendanceSession, pk=pk)
    if not request.user.has_perm('academics.delete_attendancesession'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_attendance_list')
    session.delete()
    messages.success(request, "🗑️ Attendance session deleted.")
    return redirect('academics:admin_attendance_list')


# ============================================================
# PART 18 — EXCO ADMIN — SETTINGS PAGE (Academics-wide)
# ============================================================

@login_required
def admin_academics_settings(request):
    """
    Central settings page for Academics.
    Edits SiteSettings (global toggles) + shows quick links to
    Islamiyya per-session settings.
    """
    if not request.user.has_perm('academics.change_course') and not request.user.is_superuser:
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    site_settings, _ = SiteSettings.objects.get_or_create(pk=1)
    current_islamiyya = _get_current_islamiyya_settings()

    if request.method == 'POST':
        # Only allow the toggles that already exist on SiteSettings
        site_settings.tutor_evaluations_open = 'tutor_evaluations_open' in request.POST
        site_settings.evaluation_intro_text = request.POST.get('evaluation_intro_text', '')
        site_settings.save()
        messages.success(request, "✅ Settings saved.")
        return redirect('academics:admin_academics_settings')

    return render(request, 'academics/admin/settings.html', {
        'site_settings': site_settings,
        'current_islamiyya': current_islamiyya,
        'all_islamiyya_sessions': IslamiyyaSettings.objects.all().order_by('-academic_session'),
    })


@login_required
def admin_result_edit(request, pk):
    """Edit an individual result."""
    result = get_object_or_404(Result, pk=pk)
    if not request.user.has_perm('academics.change_result'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_result_list')

    from .forms import ResultForm  # we'll add this form

    if request.method == 'POST':
        form = ResultForm(request.POST, instance=result)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Result updated for {result.student_name}.")
            return redirect('academics:admin_result_list')
    else:
        form = ResultForm(instance=result)

    return render(request, 'academics/admin/result_form.html', {
        'form': form,
        'result': result,
        'title': f'Edit Result — {result.student_name}',
        'button_text': 'Save Changes',
    })


@login_required
def admin_result_export(request):
    """Export results to Excel (respecting filters)."""
    if not request.user.has_perm('academics.view_result'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    from core.importers.spec import ColumnSpec, ImportSpec
    from core.importers.excel_io import build_export_xlsx

    qs = Result.objects.select_related('evaluation__course').order_by('student_name')
    evaluation_filter = request.GET.get('evaluation', '')
    query = request.GET.get('q', '')
    if evaluation_filter:
        qs = qs.filter(evaluation_id=evaluation_filter)
    if query:
        qs = qs.filter(Q(student_name__icontains=query) | Q(registration_number__icontains=query))

    spec = ImportSpec()
    spec.key = 'results_export'
    spec.label = 'Results Export'
    spec.columns = [
        ColumnSpec('student_name', 'Student Name'),
        ColumnSpec('registration_number', 'Reg No'),
        ColumnSpec('student_email', 'Email'),
        ColumnSpec('exam', 'Exam'),
        ColumnSpec('course', 'Course'),
        ColumnSpec('total_marks', 'Total Marks'),
        ColumnSpec('marks_obtained', 'Marks Obtained'),
        ColumnSpec('grade', 'Grade'),
        ColumnSpec('remarks', 'Remarks'),
    ]

    def row(r):
        return {
            'student_name': r.student_name,
            'registration_number': r.registration_number,
            'student_email': r.student_email or '',
            'exam': r.evaluation.title,
            'course': r.evaluation.course.name,
            'total_marks': r.evaluation.total_marks,
            'marks_obtained': float(r.marks_obtained),
            'grade': r.grade,
            'remarks': r.remarks,
        }

    spec.export_queryset = lambda: qs
    spec.row_from_instance = row
    return build_export_xlsx(spec)


def islamiyya_choose_manual_payment(request, app_id):
    """Public: student chose manual (mosque) payment. Show instructions + mark as manual."""
    registration = get_object_or_404(IslamiyyaRegistration, application_id=app_id)

    if registration.is_paid:
        messages.info(request, "You're already verified. Welcome!")
        return redirect('academics:islamiyya_dashboard')

    # Just record intent; admin will verify later
    registration.payment_method = 'manual'
    registration.save(update_fields=['payment_method'])

    return render(request, 'academics/public/islamiyya_payment_manual.html', {
        'registration': registration,
        'settings': registration.session_settings or _get_current_islamiyya_settings(),
    })

def islamiyya_slip(request, app_id):
    """Public: render the printable slip."""
    registration = get_object_or_404(IslamiyyaRegistration, application_id=app_id)
    from core.models import SiteSettings
    site = SiteSettings.objects.first()
    whatsapp_link = (
        registration.whatsapp_link
        or (registration.session_settings.whatsapp_group_link if registration.session_settings else None)
        or (site.islamiyya_whatsapp_link if site else None)
    ) if registration.is_paid else None
    return render(request, 'academics/islamiyya_application_slip.html', {
        'registration': registration,
        'whatsapp_link': whatsapp_link,
    })


# ---------- COURSES IMPORT/EXPORT ----------

@login_required
def admin_course_export(request):
    if not request.user.has_perm('academics.view_course'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_course_list')

    qs = Course.objects.prefetch_related('tutors').order_by('name')
    query = request.GET.get('q', '')
    type_filter = request.GET.get('type', '')
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if type_filter:
        qs = qs.filter(course_type=type_filter)

    spec = ImportSpec()
    spec.key = 'courses_export'
    spec.label = 'Courses'
    spec.columns = [
        ColumnSpec('name', 'Name'),
        ColumnSpec('slug', 'Slug'),
        ColumnSpec('description', 'Description'),
        ColumnSpec('course_type', 'Type'),
        ColumnSpec('tutor_emails', 'Tutor Emails'),
        ColumnSpec('is_active', 'Active'),
    ]

    def row(c):
        return {
            'name': c.name,
            'slug': c.slug,
            'description': c.description,
            'course_type': c.course_type,
            'tutor_emails': ', '.join(t.email for t in c.tutors.all() if t.email),
            'is_active': 'Yes' if c.is_active else 'No',
        }

    spec.export_queryset = lambda: qs
    spec.row_from_instance = row
    return build_export_xlsx(spec)


@login_required
def admin_course_import(request):
    if not request.user.has_perm('academics.add_course'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_course_list')

    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            messages.error(request, "Please select an Excel file.")
        else:
            try:
                from django.utils.text import slugify
                wb = openpyxl.load_workbook(excel_file)
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))
                created = updated = 0
                errors = []
                for idx, row in enumerate(rows[1:], start=2):
                    if not any(row):
                        continue
                    name = str(row[0]).strip() if row[0] else ''
                    if not name:
                        errors.append(f"Row {idx}: name is required.")
                        continue
                    slug = str(row[1]).strip() if len(row) > 1 and row[1] else slugify(name)
                    defaults = {
                        'name': name,
                        'description': str(row[2]).strip() if len(row) > 2 and row[2] else '',
                        'course_type': str(row[3]).strip().lower() if len(row) > 3 and row[3] else 'tutorial',
                        'is_active': (True if len(row) < 6 or not row[5]
                                      else str(row[5]).strip().lower() == 'yes'),
                    }
                    obj, was_created = Course.objects.update_or_create(slug=slug, defaults=defaults)
                    if was_created:
                        created += 1
                    else:
                        updated += 1
                    # Attach tutors by email
                    if len(row) > 4 and row[4]:
                        for email in [e.strip() for e in str(row[4]).split(',') if e.strip()]:
                            t = Tutor.objects.filter(email__iexact=email).first()
                            if t:
                                obj.tutors.add(t)

                messages.success(request, f"✅ {created} created, {updated} updated.")
                if errors:
                    for e in errors[:5]:
                        messages.warning(request, e)
                return redirect('academics:admin_course_list')
            except Exception as e:
                messages.error(request, f"Error reading file: {e}")

    return render(request, 'academics/admin/course_import.html')


# ---------- TUTORS IMPORT/EXPORT ----------

@login_required
def admin_tutor_export(request):
    if not request.user.has_perm('academics.view_tutor'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_tutor_list')

    qs = Tutor.objects.all().order_by('name')
    query = request.GET.get('q', '')
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(email__icontains=query))

    spec = ImportSpec()
    spec.key = 'tutors_export'
    spec.label = 'Tutors'
    spec.columns = [
        ColumnSpec('name', 'Full Name'),
        ColumnSpec('email', 'Email'),
        ColumnSpec('phone', 'Phone'),
        ColumnSpec('bio', 'Bio'),
        ColumnSpec('is_active', 'Active'),
    ]

    def row(t):
        return {
            'name': t.name,
            'email': t.email,
            'phone': t.phone,
            'bio': t.bio,
            'is_active': 'Yes' if t.is_active else 'No',
        }

    spec.export_queryset = lambda: qs
    spec.row_from_instance = row
    return build_export_xlsx(spec)


@login_required
def admin_tutor_import(request):
    if not request.user.has_perm('academics.add_tutor'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_tutor_list')

    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            messages.error(request, "Please select an Excel file.")
        else:
            try:
                wb = openpyxl.load_workbook(excel_file)
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))
                created = 0
                errors = []
                for idx, row in enumerate(rows[1:], start=2):
                    if not any(row):
                        continue
                    name = str(row[0]).strip() if row[0] else ''
                    if not name:
                        errors.append(f"Row {idx}: name is required.")
                        continue
                    email = str(row[1]).strip() if len(row) > 1 and row[1] else ''
                    if email and Tutor.objects.filter(email__iexact=email).exists():
                        errors.append(f"Row {idx}: '{email}' already exists. Skipped.")
                        continue
                    Tutor.objects.create(
                        name=name,
                        email=email,
                        phone=str(row[2]).strip() if len(row) > 2 and row[2] else '',
                        bio=str(row[3]).strip() if len(row) > 3 and row[3] else '',
                        is_active=(True if len(row) < 5 or not row[4]
                                   else str(row[4]).strip().lower() == 'yes'),
                    )
                    created += 1

                messages.success(request, f"✅ {created} tutor(s) imported.")
                if errors:
                    for e in errors[:5]:
                        messages.warning(request, e)
                return redirect('academics:admin_tutor_list')
            except Exception as e:
                messages.error(request, f"Error reading file: {e}")

    return render(request, 'academics/admin/tutor_import.html')


# ---------- RESULTS IMPORT ----------

@login_required
def admin_result_import(request):
    """
    Import results for a specific evaluation.
    Step 1: choose evaluation (dropdown)
    Step 2: upload Excel
    """
    if not request.user.has_perm('academics.add_result'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_result_list')

    evaluations = Evaluation.objects.select_related('course').order_by('-date')

    if request.method == 'POST':
        eval_id = request.POST.get('evaluation')
        excel_file = request.FILES.get('excel_file')

        if not eval_id:
            messages.error(request, "Please select which exam these results belong to.")
        elif not excel_file:
            messages.error(request, "Please select an Excel file.")
        else:
            try:
                evaluation = Evaluation.objects.get(pk=eval_id)
                wb = openpyxl.load_workbook(excel_file)
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))
                created = 0
                errors = []
                for idx, row in enumerate(rows[1:], start=2):
                    if not any(row):
                        continue
                    name = str(row[0]).strip() if row[0] else ''
                    if not name:
                        errors.append(f"Row {idx}: student name required.")
                        continue
                    reg_no = str(row[1]).strip() if len(row) > 1 and row[1] else ''
                    try:
                        marks = float(row[2]) if len(row) > 2 and row[2] is not None else 0
                    except (ValueError, TypeError):
                        errors.append(f"Row {idx}: invalid marks.")
                        continue
                    grade = str(row[3]).strip() if len(row) > 3 and row[3] else ''
                    remarks = str(row[4]).strip() if len(row) > 4 and row[4] else ''
                    Result.objects.create(
                        evaluation=evaluation,
                        student_name=name,
                        registration_number=reg_no,
                        marks_obtained=marks,
                        grade=grade,
                        remarks=remarks,
                    )
                    created += 1

                messages.success(request, f"✅ {created} result(s) imported into '{evaluation.title}'.")
                if errors:
                    for e in errors[:5]:
                        messages.warning(request, e)
                return redirect('academics:admin_result_list')
            except Evaluation.DoesNotExist:
                messages.error(request, "Selected evaluation not found.")
            except Exception as e:
                messages.error(request, f"Error reading file: {e}")

    return render(request, 'academics/admin/result_import.html', {
        'evaluations': evaluations,
    })


# ---------- ISLAMIYYA REGISTRATIONS IMPORT ----------

@login_required
def admin_islamiyya_registration_import(request):
    if not request.user.has_perm('academics.add_islamiyyaregistration'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_islamiyya_registration_list')

    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        session_id = request.POST.get('session')
        if not excel_file:
            messages.error(request, "Please select an Excel file.")
        elif not session_id:
            messages.error(request, "Please select the target session.")
        else:
            try:
                session = IslamiyyaSettings.objects.get(pk=session_id)
                wb = openpyxl.load_workbook(excel_file)
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))
                created = 0
                errors = []
                # Expected cols: Name, Email, Phone, Reg No, Dept, Gender, Level, Courses, Other, Payment Status, Amount, Method
                for idx, row in enumerate(rows[1:], start=2):
                    if not any(row):
                        continue
                    name = str(row[0]).strip() if row[0] else ''
                    email = str(row[1]).strip() if len(row) > 1 and row[1] else ''
                    if not name or not email:
                        errors.append(f"Row {idx}: name and email required.")
                        continue
                    if IslamiyyaRegistration.objects.filter(email__iexact=email).exists():
                        errors.append(f"Row {idx}: '{email}' already registered.")
                        continue
                    reg = IslamiyyaRegistration.objects.create(
                        session_settings=session,
                        name=name,
                        email=email,
                        phone=str(row[2]).strip() if len(row) > 2 and row[2] else '',
                        registration_number=str(row[3]).strip() if len(row) > 3 and row[3] else '',
                        department=str(row[4]).strip() if len(row) > 4 and row[4] else '',
                        gender=(str(row[5]).strip() if len(row) > 5 and row[5] else None),
                        level=(str(row[6]).strip().lower() if len(row) > 6 and row[6] else 'beginner'),
                        other_course=str(row[8]).strip() if len(row) > 8 and row[8] else '',
                    )
                    # Courses
                    if len(row) > 7 and row[7]:
                        for cname in [c.strip() for c in str(row[7]).split(',') if c.strip()]:
                            c, _ = IslamiyyaCourse.objects.get_or_create(name=cname)
                            reg.courses.add(c)

                    # Payment
                    ps = str(row[9]).strip().lower() if len(row) > 9 and row[9] else 'pending'
                    if ps == 'paid':
                        try:
                            amount = float(row[10]) if len(row) > 10 and row[10] else 0
                        except (ValueError, TypeError):
                            amount = 0
                        method = str(row[11]).strip().lower() if len(row) > 11 and row[11] else 'manual'
                        _complete_islamiyya_payment(reg, amount, method, reference='IMPORT')
                    elif ps == 'waived':
                        reg.mark_waived(by_user=request.user, note='Imported as waived')

                    created += 1

                messages.success(request, f"✅ {created} registration(s) imported.")
                if errors:
                    for e in errors[:5]:
                        messages.warning(request, e)
                return redirect('academics:admin_islamiyya_registration_list')
            except IslamiyyaSettings.DoesNotExist:
                messages.error(request, "Session not found.")
            except Exception as e:
                messages.error(request, f"Error reading file: {e}")

    return render(request, 'academics/admin/islamiyya_registration_import.html', {
        'sessions': IslamiyyaSettings.objects.all().order_by('-academic_session'),
    })


# ---------- COMPETITION EXPORT ----------

@login_required
def admin_competition_export(request):
    if not request.user.has_perm('academics.view_competitionresult'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_competition_list')

    qs = CompetitionResult.objects.all().order_by('event_name', 'category', 'order', 'position')
    event_filter = request.GET.get('event', '')
    if event_filter:
        qs = qs.filter(event_name=event_filter)

    spec = ImportSpec()
    spec.key = 'competition_export'
    spec.label = 'Competition Results'
    spec.columns = [
        ColumnSpec('event_name', 'Event Name'),
        ColumnSpec('category', 'Category'),
        ColumnSpec('position', 'Position'),
        ColumnSpec('participant_name', 'Participant Name'),
        ColumnSpec('department', 'Department'),
        ColumnSpec('points', 'Points'),
        ColumnSpec('year', 'Year'),
        ColumnSpec('order', 'Order'),
    ]

    def row(r):
        return {
            'event_name': r.event_name,
            'category': r.category,
            'position': r.position,
            'participant_name': r.participant_name,
            'department': r.department,
            'points': r.points,
            'year': r.year,
            'order': r.order,
        }

    spec.export_queryset = lambda: qs
    spec.row_from_instance = row
    return build_export_xlsx(spec)


# ---------- RESOURCE ADMIN CREATE ----------

@login_required
def admin_resource_create(request):
    """Admin can directly add a resource (already approved)."""
    if not request.user.has_perm('academics.add_userresourcesubmission'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_resource_list')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        submitted_by = request.POST.get('submitted_by', '').strip()
        email = request.POST.get('email', '').strip()
        file = request.FILES.get('file')

        if not title or not description or not file:
            messages.error(request, "Title, description, and file are required.")
        else:
            resource = UserResourceSubmission.objects.create(
                title=title,
                description=description,
                submitted_by=submitted_by,
                email=email,
                file=file,
                status='approved',  # Admin-added resources are auto-approved
                reviewed_at=timezone.now(),
                reviewed_by=request.user,
                review_note='Added directly by EXCO',
            )
            messages.success(request, f"✅ Resource '{resource.title}' added.")
            return redirect('academics:admin_resource_list')

    return render(request, 'academics/admin/resource_form.html', {
        'title': 'Add Resource',
        'button_text': 'Add Resource',
    })


# ---------- ATTENDANCE IMPORT/EXPORT ----------

@login_required
def admin_attendance_export(request):
    """Export all attendance records, filtered by session type."""
    if not request.user.has_perm('academics.view_attendancesession'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_attendance_list')

    type_filter = request.GET.get('type', '')
    records = AttendanceRecord.objects.select_related(
        'session', 'user', 'islamiyya_registration'
    ).order_by('-session__date')

    if type_filter:
        records = records.filter(session__session_type=type_filter)

    spec = ImportSpec()
    spec.key = 'attendance_export'
    spec.label = 'Attendance'
    spec.columns = [
        ColumnSpec('session_title', 'Session Title'),
        ColumnSpec('session_type', 'Session Type'),
        ColumnSpec('session_date', 'Session Date'),
        ColumnSpec('attendee_name', 'Attendee Name'),
        ColumnSpec('attendee_role', 'Role'),
        ColumnSpec('present', 'Present'),
    ]

    def row(r):
        return {
            'session_title': r.session.title,
            'session_type': r.session.get_session_type_display(),
            'session_date': r.session.date.strftime('%Y-%m-%d'),
            'attendee_name': r.display_name,
            'attendee_role': r.display_role,
            'present': 'Yes' if r.present else 'No',
        }

    spec.export_queryset = lambda: records
    spec.row_from_instance = row
    return build_export_xlsx(spec)


@login_required
def admin_attendance_session_export(request, pk):
    """Export one session's attendance sheet."""
    session = get_object_or_404(AttendanceSession, pk=pk)
    if not request.user.has_perm('academics.view_attendancesession'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_attendance_list')

    records = session.records.all()

    spec = ImportSpec()
    spec.key = 'session_attendance_export'
    spec.label = f'Attendance — {session.title}'
    spec.columns = [
        ColumnSpec('attendee_name', 'Name'),
        ColumnSpec('attendee_role', 'Role'),
        ColumnSpec('present', 'Present'),
    ]

    def row(r):
        return {
            'attendee_name': r.display_name,
            'attendee_role': r.display_role,
            'present': 'Yes' if r.present else 'No',
        }

    spec.export_queryset = lambda: records
    spec.row_from_instance = row
    return build_export_xlsx(spec)


@login_required
def admin_attendance_session_import(request, pk):
    """Bulk import attendees for a specific session."""
    session = get_object_or_404(AttendanceSession, pk=pk)
    if not request.user.has_perm('academics.change_attendancesession'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_attendance_list')

    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            messages.error(request, "Please select an Excel file.")
        else:
            try:
                wb = openpyxl.load_workbook(excel_file)
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))
                created = 0
                errors = []
                # Expected: Name, Role, Present
                for idx, row in enumerate(rows[1:], start=2):
                    if not any(row):
                        continue
                    name = str(row[0]).strip() if row[0] else ''
                    if not name:
                        errors.append(f"Row {idx}: name is required.")
                        continue
                    role = str(row[1]).strip() if len(row) > 1 and row[1] else ''
                    present = True if len(row) < 3 or not row[2] else str(row[2]).strip().lower() in ('yes', 'true', '1', 'present')
                    AttendanceRecord.objects.create(
                        session=session,
                        manual_name=name,
                        manual_role=role,
                        present=present,
                    )
                    created += 1

                messages.success(request, f"✅ {created} attendee(s) imported.")
                if errors:
                    for e in errors[:5]:
                        messages.warning(request, e)
                return redirect('academics:admin_attendance_edit', pk=session.pk)
            except Exception as e:
                messages.error(request, f"Error reading file: {e}")

    return render(request, 'academics/admin/attendance_import.html', {
        'session': session,
    })


@login_required
def admin_attendance_import(request):
    """Global attendance import (optional). Expects columns: Session Title, Name, Role, Present."""
    if not request.user.has_perm('academics.add_attendancerecord'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_attendance_list')

    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            messages.error(request, "Please select an Excel file.")
        else:
            try:
                wb = openpyxl.load_workbook(excel_file)
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))
                created = 0
                errors = []
                for idx, row in enumerate(rows[1:], start=2):
                    if not any(row):
                        continue
                    session_title = str(row[0]).strip() if row[0] else ''
                    name = str(row[1]).strip() if len(row) > 1 and row[1] else ''
                    role = str(row[2]).strip() if len(row) > 2 and row[2] else ''
                    present = True if len(row) < 4 or not row[3] else str(row[3]).strip().lower() in ('yes', 'true', '1')
                    if not session_title or not name:
                        errors.append(f"Row {idx}: session title and name required.")
                        continue
                    session = AttendanceSession.objects.filter(title__iexact=session_title).first()
                    if not session:
                        errors.append(f"Row {idx}: session '{session_title}' not found.")
                        continue
                    AttendanceRecord.objects.create(
                        session=session,
                        manual_name=name,
                        manual_role=role,
                        present=present,
                    )
                    created += 1
                messages.success(request, f"✅ {created} attendance record(s) imported.")
                if errors:
                    for e in errors[:5]:
                        messages.warning(request, e)
                return redirect('academics:admin_attendance_list')
            except Exception as e:
                messages.error(request, f"Error reading file: {e}")

    return render(request, 'academics/admin/attendance_import.html', {
        'global_import': True,
    })



# ============================================================
# LIBRARY — VIEWS
# ============================================================

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from datetime import timedelta

from .models import Book, BookCategory


# ---------- helpers ----------

def _user_can_manage_library(user):
    """Staff, superuser, or any active office containing 'librar'."""
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return user.office_assignments.filter(
        is_active=True,
        office__name__icontains='librar',
    ).exists()


def _library_stats():
    return {
        'total_books': Book.objects.filter(inventory_item__is_active=True).count(),
        'total_available': Book.objects.filter(
            status=Book.STATUS_AVAILABLE,
            inventory_item__is_active=True,
        ).count(),
        'total_borrowed': Book.objects.filter(
            status=Book.STATUS_BORROWED,
        ).count(),
        'total_categories': BookCategory.objects.count(),
    }


# ============================================================
# PUBLIC
# ============================================================

def library_home(request):
    """Public catalog — anyone can browse."""
    qs = Book.objects.select_related(
        'inventory_item', 'category'
    ).filter(inventory_item__is_active=True)

    q = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()
    availability = request.GET.get('availability', '').strip()
    book_format = request.GET.get('format', '').strip()
    sort = request.GET.get('sort', 'title').strip()

    if q:
        qs = qs.filter(
            Q(inventory_item__name__icontains=q)
            | Q(author__icontains=q)
            | Q(isbn__icontains=q)
            | Q(publisher__icontains=q)
        )
    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    if availability == 'available':
        qs = qs.filter(status=Book.STATUS_AVAILABLE)
    elif availability == 'borrowed':
        qs = qs.filter(status=Book.STATUS_BORROWED)
    if book_format:
        qs = qs.filter(book_format=book_format)

    # Sort
    if sort == 'recent':
        qs = qs.order_by('-created_at')
    elif sort == 'author':
        qs = qs.order_by('author', 'inventory_item__name')
    elif sort == 'popular':
        qs = qs.order_by('-is_featured', 'inventory_item__name')
    else:
        qs = qs.order_by('inventory_item__name')

    featured = Book.objects.filter(
        is_featured=True,
        inventory_item__is_active=True,
    ).select_related('inventory_item', 'category')[:6]

    categories = BookCategory.objects.annotate(
        count=Count('books', filter=Q(books__inventory_item__is_active=True))
    ).order_by('order', 'name')

    page = Paginator(qs, 24).get_page(request.GET.get('page'))

    context = {
        'books': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'q': q,
        'category_slug': category_slug,
        'availability': availability,
        'book_format': book_format,
        'sort': sort,
        'categories': categories,
        'featured': featured,
        **_library_stats(),
    }
    return render(request, 'academics/library_home.html', context)


def library_book_detail(request, pk):
    """Single book page."""
    book = get_object_or_404(
        Book.objects.select_related('inventory_item', 'category'),
        pk=pk, inventory_item__is_active=True,
    )

    related = Book.objects.none()
    if book.category:
        related = Book.objects.filter(
            category=book.category,
            inventory_item__is_active=True,
        ).exclude(pk=book.pk).select_related('inventory_item', 'category')[:4]

    can_borrow = (
        request.user.is_authenticated
        and book.is_borrowable
        and book.is_available
        and book.current_borrower_id != request.user.id
        and book.is_physical
    )
    already_borrowed = (
        request.user.is_authenticated
        and book.current_borrower_id == request.user.id
    )

    return render(request, 'academics/library_detail.html', {
        'book': book,
        'related': related,
        'can_borrow': can_borrow,
        'already_borrowed': already_borrowed,
    })


# ============================================================
# BORROWING (members only)
# ============================================================

@login_required
def library_borrow(request, pk):
    book = get_object_or_404(Book, pk=pk)

    if request.method != 'POST':
        return redirect('academics:library_detail', pk=pk)

    if not book.is_borrowable:
        messages.error(request, "This book is reference-only and cannot be borrowed.")
        return redirect('academics:library_detail', pk=pk)
    if not book.is_physical:
        messages.error(request, "This is a digital-only resource — use the download link.")
        return redirect('academics:library_detail', pk=pk)
    if not book.is_available:
        messages.error(request, "This book is not currently available.")
        return redirect('academics:library_detail', pk=pk)
    if book.current_borrower_id == request.user.id:
        messages.warning(request, "You already have this book.")
        return redirect('academics:library_detail', pk=pk)

    overdue = Book.objects.filter(
        current_borrower=request.user,
        status=Book.STATUS_BORROWED,
        due_date__lt=timezone.now().date(),
    ).exists()
    if overdue:
        messages.error(
            request,
            "You have overdue books. Please return them before borrowing more."
        )
        return redirect('academics:library_detail', pk=pk)

    book.status = Book.STATUS_BORROWED
    book.current_borrower = request.user
    book.borrowed_at = timezone.now()
    book.due_date = (timezone.now() + timedelta(days=book.loan_days)).date()
    book.save(update_fields=['status', 'current_borrower', 'borrowed_at', 'due_date'])

    messages.success(
        request,
        f"✅ You borrowed “{book.title}”. Due {book.due_date.strftime('%b %d, %Y')}."
    )
    return redirect('academics:library_my_books')


@login_required
def library_return(request, pk):
    book = get_object_or_404(Book, pk=pk)
    is_staff = _user_can_manage_library(request.user)

    if book.current_borrower_id != request.user.id and not is_staff:
        messages.error(request, "You can only return books you borrowed.")
        return redirect('academics:library_detail', pk=pk)

    if request.method != 'POST':
        return redirect('academics:library_detail', pk=pk)

    book.status = Book.STATUS_AVAILABLE
    book.current_borrower = None
    book.borrowed_at = None
    book.due_date = None
    book.save(update_fields=['status', 'current_borrower', 'borrowed_at', 'due_date'])

    messages.success(request, f"✅ “{book.title}” has been returned.")
    if is_staff and book.current_borrower_id != request.user.id:
        return redirect('academics:library_manage')
    return redirect('academics:library_my_books')


@login_required
def library_my_books(request):
    """Current user's borrowed books."""
    borrowed = Book.objects.filter(
        current_borrower=request.user,
    ).select_related('inventory_item', 'category').order_by('due_date')

    overdue_qs = borrowed.filter(due_date__lt=timezone.now().date())

    return render(request, 'academics/library_my_books.html', {
        'borrowed': borrowed,
        'overdue_count': overdue_qs.count(),
        'due_soon_count': borrowed.filter(
            due_date__gte=timezone.now().date(),
            due_date__lte=timezone.now().date() + timedelta(days=3),
        ).count(),
    })

# ============================================================
# LIBRARY — E-LIBRARY VIEWS (browse + download only)
# ============================================================

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.shortcuts import render, redirect, get_object_or_404

from .models import Book, BookCategory


def _user_can_manage_library(user):
    """Staff, superuser, or any active office."""
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return user.office_assignments.filter(is_active=True).exists()


# ---------- PUBLIC: browse the library ----------

def library_home(request):
    """Public catalog — anyone can browse and download."""
    qs = Book.objects.select_related(
        'category', 'uploaded_by'
    ).filter(is_published=True)

    q = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()
    sort = request.GET.get('sort', 'title').strip()

    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(author__icontains=q)
            | Q(isbn__icontains=q)
            | Q(publisher__icontains=q)
            | Q(description__icontains=q)
        )
    if category_slug:
        qs = qs.filter(category__slug=category_slug)

    if sort == 'recent':
        qs = qs.order_by('-created_at')
    elif sort == 'author':
        qs = qs.order_by('author', 'title')
    else:
        qs = qs.order_by('order', 'title')

    featured = Book.objects.filter(
        is_featured=True, is_published=True
    ).select_related('category')[:6]

    categories = BookCategory.objects.annotate(
        count=Count('books', filter=Q(books__is_published=True))
    ).order_by('order', 'name')

    page = Paginator(qs, 24).get_page(request.GET.get('page'))

    return render(request, 'academics/library_home.html', {
        'books': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'q': q,
        'category_slug': category_slug,
        'sort': sort,
        'categories': categories,
        'featured': featured,
        'total_books': Book.objects.filter(is_published=True).count(),
        'total_categories': categories.count(),
    })


def library_book_detail(request, pk):
    """Book detail page with download button and inline PDF preview."""
    book = get_object_or_404(
        Book.objects.select_related('category', 'uploaded_by'),
        pk=pk, is_published=True,
    )

    related = Book.objects.none()
    if book.category:
        related = Book.objects.filter(
            category=book.category, is_published=True,
        ).exclude(pk=book.pk).select_related('category')[:4]

    return render(request, 'academics/library_detail.html', {
        'book': book,
        'related': related,
    })


# ---------- MANAGE: staff/EXCO ----------

@login_required
def library_manage(request):
    """Staff dashboard — list, filter, add, edit, delete."""
    if not _user_can_manage_library(request.user):
        messages.error(request, "Library management requires staff access.")
        return redirect('academics:library_home')

    qs = Book.objects.select_related('category').order_by('-created_at')

    q = request.GET.get('q', '').strip()
    cat_filter = request.GET.get('category', '').strip()
    publish_filter = request.GET.get('published', '').strip()

    if q:
        qs = qs.filter(
            Q(title__icontains=q) | Q(author__icontains=q)
        )
    if cat_filter:
        qs = qs.filter(category__slug=cat_filter)
    if publish_filter == 'published':
        qs = qs.filter(is_published=True)
    elif publish_filter == 'draft':
        qs = qs.filter(is_published=False)

    page = Paginator(qs, 25).get_page(request.GET.get('page'))
    categories = BookCategory.objects.order_by('order', 'name')

    return render(request, 'academics/library_manage.html', {
        'books': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'q': q,
        'cat_filter': cat_filter,
        'publish_filter': publish_filter,
        'categories': categories,
        'total_books': Book.objects.count(),
        'total_published': Book.objects.filter(is_published=True).count(),
        'total_drafts': Book.objects.filter(is_published=False).count(),
        'total_featured': Book.objects.filter(is_featured=True).count(),
    })


@login_required
def library_book_form(request, pk=None):
    """Add or edit a book."""
    if not _user_can_manage_library(request.user):
        messages.error(request, "Library management requires staff access.")
        return redirect('academics:library_home')

    book = get_object_or_404(Book, pk=pk) if pk else None

    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()

        if not title:
            messages.error(request, "Book title is required.")
        else:
            def _int(name, default=None):
                raw = (request.POST.get(name) or '').strip()
                return int(raw) if raw.isdigit() else default

            is_new = book is None
            if is_new:
                book = Book(uploaded_by=request.user)

            book.title = title
            book.description = (request.POST.get('description') or '').strip()
            book.author = (request.POST.get('author') or '').strip()
            book.isbn = (request.POST.get('isbn') or '').strip()
            book.publisher = (request.POST.get('publisher') or '').strip()
            book.publication_year = _int('publication_year')
            book.edition = (request.POST.get('edition') or '').strip()
            book.pages = _int('pages')
            book.language = (request.POST.get('language') or 'English').strip() or 'English'
            book.external_cover_url = (request.POST.get('external_cover_url') or '').strip()
            book.external_file_url = (request.POST.get('external_file_url') or '').strip()
            book.external_file_label = (
                (request.POST.get('external_file_label') or '').strip() or 'Download'
            )
            book.is_featured = 'is_featured' in request.POST
            book.is_published = 'is_published' in request.POST
            book.order = _int('order', 0) or 0

            cat_id = (request.POST.get('category') or '').strip()
            book.category = (
                BookCategory.objects.filter(pk=cat_id).first() if cat_id else None
            )

            # Cover upload
            new_cover = request.FILES.get('cover_image')
            if new_cover:
                if book.pk and book.cover_image:
                    try:
                        book.cover_image.delete(save=False)
                    except Exception:
                        pass
                book.cover_image = new_cover

            # File upload
            new_file = request.FILES.get('file')
            if new_file:
                if book.pk and book.file:
                    try:
                        book.file.delete(save=False)
                    except Exception:
                        pass
                book.file = new_file

            # Require at least one file source
            if not book.external_file_url and not book.file:
                messages.error(request, "Please upload a file or provide an external download link.")
            else:
                book.save()
                messages.success(request, f"✅ “{book.title}” saved.")
                return redirect('academics:library_manage')

    categories = BookCategory.objects.order_by('order', 'name')

    return render(request, 'academics/library_book_form.html', {
        'book': book,
        'categories': categories,
    })


@login_required
def library_book_delete(request, pk):
    """Delete a book."""
    if not _user_can_manage_library(request.user):
        messages.error(request, "Library management requires staff access.")
        return redirect('academics:library_home')

    book = get_object_or_404(Book, pk=pk)

    if request.method == 'POST':
        title = book.title
        for field in (book.cover_image, book.file):
            try:
                if field:
                    field.delete(save=False)
            except Exception:
                pass
        book.delete()
        messages.success(request, f"🗑️ “{title}” removed from library.")
        return redirect('academics:library_manage')

    return render(request, 'academics/library_book_delete.html', {'book': book})


@login_required
def library_category_manage(request):
    """Manage categories."""
    if not _user_can_manage_library(request.user):
        messages.error(request, "Library management requires staff access.")
        return redirect('academics:library_home')

    if request.method == 'POST':
        action = request.POST.get('action', '')
        name = (request.POST.get('name') or '').strip()
        icon = (request.POST.get('icon') or '').strip()
        color = (request.POST.get('color') or '#0F3D2E').strip() or '#0F3D2E'
        description = (request.POST.get('description') or '').strip()
        order_raw = (request.POST.get('order') or '0').strip()
        order = int(order_raw) if order_raw.isdigit() else 0

        if action == 'delete':
            cat_id = request.POST.get('category_id', '')
            cat = BookCategory.objects.filter(pk=cat_id).first()
            if cat:
                cat.delete()
                messages.success(request, "Category deleted.")
        elif name:
            cat_id = request.POST.get('category_id', '')
            if cat_id:
                cat = BookCategory.objects.filter(pk=cat_id).first()
                if cat:
                    cat.name = name
                    cat.icon = icon
                    cat.color = color
                    cat.description = description
                    cat.order = order
                    cat.save()
                    messages.success(request, f"Updated “{name}”.")
            else:
                BookCategory.objects.create(
                    name=name, icon=icon, color=color,
                    description=description, order=order,
                )
                messages.success(request, f"Created “{name}”.")
        return redirect('academics:library_category_manage')

    categories = BookCategory.objects.annotate(
        count=Count('books')
    ).order_by('order', 'name')

    return render(request, 'academics/library_category_manage.html', {
        'categories': categories,
    })
    
    
# ============================================================
# CBT ANTI-CHEATING
# ============================================================

import json
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import CBTViolation, CBTCourse


@login_required
@require_POST
def cbt_log_violation(request):
    """
    Receives a violation event from the CBT anti-cheating module.
    Logs it and tells the client whether to auto-submit (3+ strikes).
    """
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    attempt_id = (data.get('attempt_id') or '').strip()
    vtype = (data.get('violation_type') or '').strip()
    metadata = data.get('metadata') or {}
    course_id = data.get('course_id')

    if not attempt_id or not vtype:
        return JsonResponse({'ok': False, 'error': 'Missing required fields'}, status=400)

    valid_types = {code for code, _ in CBTViolation.VIOLATION_TYPES}
    if vtype not in valid_types:
        return JsonResponse({'ok': False, 'error': 'Unknown violation type'}, status=400)

    course = CBTCourse.objects.filter(pk=course_id).first() if course_id else None

    # Count violations BEFORE we save this one, so we know the sequence
    prior_count = CBTViolation.objects.filter(attempt_id=attempt_id).count()
    new_count = prior_count + 1
    will_trigger_submit = new_count >= 3

    CBTViolation.objects.create(
        attempt_id=attempt_id,
        user=request.user,
        course=course,
        violation_type=vtype,
        metadata=metadata if isinstance(metadata, dict) else {},
        triggered_submit=will_trigger_submit,
    )

    return JsonResponse({
        'ok': True,
        'total': new_count,
        'should_submit': will_trigger_submit,
        'remaining': max(0, 3 - new_count),
    })    
    
    
    
    
    
    