"""
CBT (Computer-Based Testing) views — admin + public.

All CBT views live here to keep academics/views.py clean.
Imported by academics/urls.py.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Q, F, Count
from django.http import (
    HttpResponse, JsonResponse, HttpResponseBadRequest,
)
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST, require_GET

import openpyxl

from .models import CBTCourse, QuestionBank


# ============================================================
# HELPERS — SiteSettings access
# ============================================================

def _site_settings():
    """Return the SiteSettings singleton or None."""
    try:
        from core.models import SiteSettings
        return SiteSettings.objects.first()
    except Exception:
        return None


def _cbt_enabled() -> bool:
    s = _site_settings()
    return bool(s and s.cbt_enabled)


def _cbt_flag(name: str, default=False):
    """Read a cbt_* flag from SiteSettings."""
    s = _site_settings()
    if not s:
        return default
    return getattr(s, name, default)


def _cbt_ai_report_enabled() -> bool:
    return _cbt_enabled() and _cbt_flag('cbt_ai_report_enabled', False)


def _cbt_show_answers() -> bool:
    return _cbt_flag('cbt_show_answers', True)


def _cbt_allow_retake() -> bool:
    return _cbt_flag('cbt_allow_retake', True)


def _cbt_allow_difficulty() -> bool:
    return _cbt_flag('cbt_allow_difficulty_choice', True)


def _cbt_allow_topic() -> bool:
    return _cbt_flag('cbt_allow_topic_filter', False)


def _cbt_default_count() -> int:
    return int(_cbt_flag('cbt_default_question_count', 20) or 20)


def _cbt_default_minutes() -> int:
    return int(_cbt_flag('cbt_default_time_minutes', 20) or 20)


def _cbt_min_questions() -> int:
    return int(_cbt_flag('cbt_min_questions', 5) or 5)


def _cbt_max_questions() -> int:
    return int(_cbt_flag('cbt_max_questions', 50) or 50)


def _cbt_grace_seconds() -> int:
    return int(_cbt_flag('cbt_grace_seconds', 30) or 30)


def _cbt_tab_switch_threshold() -> int:
    return int(_cbt_flag('cbt_tab_switch_warning_threshold', 3) or 3)


# ============================================================
# HELPERS — Session management
# ============================================================

CBT_TEST_KEY = 'cbt_test'
CBT_RESULT_KEY = 'cbt_result'
CBT_AI_COUNT_KEY = 'cbt_ai_report_count'


def _clear_cbt_session(request):
    """Remove any prior CBT state — called whenever a new test starts."""
    for key in (CBT_TEST_KEY, CBT_RESULT_KEY):
        request.session.pop(key, None)


def _get_active_test(request):
    """Return the current cbt_test dict or None."""
    return request.session.get(CBT_TEST_KEY)


def _test_seconds_elapsed(test: dict) -> int:
    try:
        started = timezone.datetime.fromisoformat(test['started_at'])
    except Exception:
        return 0
    return int((timezone.now() - started).total_seconds())


def _test_time_left(test: dict) -> int:
    """Seconds left; can go negative if past grace."""
    return int(test['time_limit_seconds']) - _test_seconds_elapsed(test)


def _test_is_expired(test: dict) -> bool:
    """True if student is past time limit + grace window."""
    return _test_time_left(test) < -_cbt_grace_seconds()


# ============================================================
# HELPERS — Question selection (randomization)
# ============================================================

def _build_question_pool(course: CBTCourse, difficulty: str = 'mixed',
                         topic: str = '') -> list[int]:
    """Return a list of active question IDs matching the filters."""
    qs = QuestionBank.objects.filter(course=course, is_active=True)
    if difficulty and difficulty != 'mixed':
        qs = qs.filter(difficulty=difficulty)
    if topic:
        qs = qs.filter(topic__iexact=topic)
    return list(qs.values_list('id', flat=True))


def _pick_random_questions(pool: list[int], count: int) -> list[int]:
    """Pick `count` unique random IDs from pool. Shuffled by random.sample."""
    count = max(1, min(count, len(pool)))
    return random.sample(pool, count)


# ============================================================
# HELPERS — Grading + stats
# ============================================================

def _grade_test(test: dict, answers: dict) -> dict:
    """
    Compute score + breakdown from a test dict and answers map.
    answers: { '<qid>': 'a'|'b'|'c'|'d'|None }
    Returns a result dict.
    """
    ids = test['question_ids']
    questions = {q.id: q for q in QuestionBank.objects.filter(id__in=ids)}

    correct_ids, wrong_ids, unanswered_ids = [], [], []
    per_difficulty = defaultdict(lambda: {'correct': 0, 'total': 0})
    per_topic = defaultdict(lambda: {'correct': 0, 'total': 0})

    for qid in ids:
        q = questions.get(qid)
        if not q:
            continue
        ans = answers.get(str(qid))
        topic_key = q.topic or 'General'

        per_difficulty[q.difficulty]['total'] += 1
        per_topic[topic_key]['total'] += 1

        if ans is None:
            unanswered_ids.append(qid)
        elif ans == q.correct_option:
            correct_ids.append(qid)
            per_difficulty[q.difficulty]['correct'] += 1
            per_topic[topic_key]['correct'] += 1
        else:
            wrong_ids.append(qid)

    total = len(ids)
    score = len(correct_ids)
    pct = round((score / total) * 100, 1) if total else 0.0

    return {
        'score': score,
        'total': total,
        'percentage': pct,
        'band': _score_band(pct),
        'correct_ids': correct_ids,
        'wrong_ids': wrong_ids,
        'unanswered_ids': unanswered_ids,
        'per_difficulty': {k: dict(v) for k, v in per_difficulty.items()},
        'per_topic': {k: dict(v) for k, v in per_topic.items()},
    }


def _score_band(pct: float) -> str:
    if pct >= 80:
        return 'excellent'
    if pct >= 60:
        return 'good'
    if pct >= 40:
        return 'fair'
    return 'needs_work'


def _increment_question_stats(question_ids: list[int], answers: dict, questions: dict):
    """
    Update times_answered / times_correct with F() expressions to avoid
    race conditions when many students submit at once.
    """
    for qid in question_ids:
        q = questions.get(qid)
        if not q:
            continue
        ans = answers.get(str(qid))
        is_correct = (ans == q.correct_option)
        QuestionBank.objects.filter(pk=qid).update(
            times_answered=F('times_answered') + 1,
            times_correct=F('times_correct') + (1 if is_correct else 0),
        )


# ============================================================
# ============ ADMIN VIEWS (EXCO custom templates) ============
# ============================================================

# ---------- Dashboard ----------
@login_required
def admin_cbt_dashboard(request):
    if not request.user.has_perm('academics.view_questionbank'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    from django.db.models import Sum, Avg

    total_courses = CBTCourse.objects.count()
    active_courses = CBTCourse.objects.filter(is_active=True).count()
    total_questions = QuestionBank.objects.count()
    active_questions = QuestionBank.objects.filter(is_active=True).count()

    # Difficulty counts (for doughnut)
    qs_active = QuestionBank.objects.filter(is_active=True)
    easy_count = qs_active.filter(difficulty='easy').count()
    medium_count = qs_active.filter(difficulty='medium').count()
    hard_count = qs_active.filter(difficulty='hard').count()

    # Per-course counts (for bar chart) — top 8 courses
    all_courses = CBTCourse.objects.filter(is_active=True).annotate(
        q_count=Count('questions', filter=Q(questions__is_active=True))
    ).order_by('-q_count')[:8]
    all_courses_json = [{'name': c.name, 'count': c.q_count} for c in all_courses]

    # Overall aggregate stats
    agg = QuestionBank.objects.aggregate(
        total_answers=Sum('times_answered'),
        total_correct=Sum('times_correct'),
    )
    total_attempts = agg['total_answers'] or 0
    overall_correct_rate = None
    if total_attempts and agg['total_correct'] is not None:
        overall_correct_rate = round((agg['total_correct'] / total_attempts) * 100, 1)

    # Courses low on questions
    short_courses = (
        CBTCourse.objects.filter(is_active=True)
        .annotate(q_count=Count('questions', filter=Q(questions__is_active=True)))
        .filter(q_count__lt=20)
        .order_by('q_count')[:6]
    )

    # Low performers
    low_performers = (
        QuestionBank.objects.filter(
            is_active=True, times_answered__gte=5,
            times_correct__lt=F('times_answered') * 0.4,
        ).select_related('course')
        .order_by('times_correct')[:8]
    )

    # Recent
    recent = (
        QuestionBank.objects.select_related('course')
        .order_by('-created_at')[:8]
    )

    settings_obj = _site_settings()

    return render(request, 'academics/admin/cbt/dashboard.html', {
        'total_courses': total_courses,
        'active_courses': active_courses,
        'total_questions': total_questions,
        'active_questions': active_questions,
        'easy_count': easy_count,
        'medium_count': medium_count,
        'hard_count': hard_count,
        'all_courses_json': all_courses_json,
        'overall_correct_rate': overall_correct_rate,
        'total_attempts': total_attempts,
        'short_courses': short_courses,
        'low_performers': low_performers,
        'recent': recent,
        'settings': settings_obj,
        'cbt_enabled': _cbt_enabled(),
    })

# ---------- CBT Course CRUD ----------

@login_required
def admin_cbt_course_list(request):
    if not request.user.has_perm('academics.view_cbtcourse'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_dashboard')

    qs = (
        CBTCourse.objects
        .annotate(
            q_total=Count('questions', filter=Q(questions__is_active=True)),
        )
        .order_by('order', 'name')
    )

    query = request.GET.get('q', '').strip()
    active_filter = request.GET.get('active', '')
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if active_filter == 'yes':
        qs = qs.filter(is_active=True)
    elif active_filter == 'no':
        qs = qs.filter(is_active=False)

    page = Paginator(qs, 30).get_page(request.GET.get('page'))

    return render(request, 'academics/admin/cbt/course_list.html', {
        'courses': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'query': query,
        'active_filter': active_filter,
    })


@login_required
def admin_cbt_course_create(request):
    if not request.user.has_perm('academics.add_cbtcourse'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_cbt_course_list')

    from .forms import CBTCourseForm  # built in support files

    if request.method == 'POST':
        form = CBTCourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.created_by = request.user
            if not course.slug:
                course.slug = slugify(course.name)[:200] or 'course'
            course.save()
            messages.success(request, f"✅ CBT course '{course.name}' created.")
            return redirect('academics:admin_cbt_course_list')
        messages.error(request, "Please fix the errors below.")
    else:
        form = CBTCourseForm()

    return render(request, 'academics/admin/cbt/course_form.html', {
        'form': form,
        'title': 'Add CBT Course',
        'button_text': 'Create Course',
    })


@login_required
def admin_cbt_course_edit(request, pk):
    course = get_object_or_404(CBTCourse, pk=pk)
    if not request.user.has_perm('academics.change_cbtcourse'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_cbt_course_list')

    from .forms import CBTCourseForm

    if request.method == 'POST':
        form = CBTCourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ CBT course '{course.name}' updated.")
            return redirect('academics:admin_cbt_course_list')
        messages.error(request, "Please fix the errors below.")
    else:
        form = CBTCourseForm(instance=course)

    return render(request, 'academics/admin/cbt/course_form.html', {
        'form': form,
        'course': course,
        'title': f'Edit — {course.name}',
        'button_text': 'Save Changes',
    })


@require_POST
@login_required
def admin_cbt_course_delete(request, pk):
    course = get_object_or_404(CBTCourse, pk=pk)
    if not request.user.has_perm('academics.delete_cbtcourse'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_cbt_course_list')
    name = course.name
    course.delete()
    messages.success(request, f"🗑️ CBT course '{name}' deleted.")
    return redirect('academics:admin_cbt_course_list')


@require_POST
@login_required
def admin_cbt_course_toggle(request, pk):
    course = get_object_or_404(CBTCourse, pk=pk)
    if not request.user.has_perm('academics.change_cbtcourse'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_cbt_course_list')
    course.is_active = not course.is_active
    course.save(update_fields=['is_active'])
    state = 'activated' if course.is_active else 'deactivated'
    messages.success(request, f"'{course.name}' {state}.")
    return redirect('academics:admin_cbt_course_list')


# ---------- Question CRUD ----------

@login_required
def admin_question_list(request):
    if not request.user.has_perm('academics.view_questionbank'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_cbt_dashboard')

    qs = (
        QuestionBank.objects
        .select_related('course', 'created_by')
        .order_by('-created_at')
    )

    course_filter = request.GET.get('course', '')
    difficulty_filter = request.GET.get('difficulty', '')
    topic_filter = request.GET.get('topic', '').strip()
    source_filter = request.GET.get('source', '')
    active_filter = request.GET.get('active', '')
    query = request.GET.get('q', '').strip()
    quality_filter = request.GET.get('quality', '')

    if course_filter:
        qs = qs.filter(course_id=course_filter)
    if difficulty_filter:
        qs = qs.filter(difficulty=difficulty_filter)
    if topic_filter:
        qs = qs.filter(topic__iexact=topic_filter)
    if source_filter:
        qs = qs.filter(source=source_filter)
    if active_filter == 'yes':
        qs = qs.filter(is_active=True)
    elif active_filter == 'no':
        qs = qs.filter(is_active=False)
    if query:
        qs = qs.filter(
            Q(question_text__icontains=query) |
            Q(option_a__icontains=query) |
            Q(option_b__icontains=query) |
            Q(option_c__icontains=query) |
            Q(option_d__icontains=query)
        )
    if quality_filter == 'low':
        qs = qs.filter(times_answered__gte=5, times_correct__lt=F('times_answered') * 0.4)
    elif quality_filter == 'high':
        qs = qs.filter(times_answered__gte=5, times_correct__gte=F('times_answered') * 0.85)
    elif quality_filter == 'never':
        qs = qs.filter(times_answered=0)

    page = Paginator(qs, 30).get_page(request.GET.get('page'))

    # Distinct topics for filter dropdown
    topics = (
        QuestionBank.objects
        .exclude(topic='')
        .values_list('topic', flat=True)
        .distinct().order_by('topic')
    )

    return render(request, 'academics/admin/cbt/question_list.html', {
        'questions': page,
        'page_obj': page,
        'is_paginated': page.has_other_pages(),
        'courses': CBTCourse.objects.order_by('order', 'name'),
        'topics': topics,
        'course_filter': course_filter,
        'difficulty_filter': difficulty_filter,
        'topic_filter': topic_filter,
        'source_filter': source_filter,
        'active_filter': active_filter,
        'quality_filter': quality_filter,
        'query': query,
    })


@login_required
def admin_question_create(request):
    if not request.user.has_perm('academics.add_questionbank'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_question_list')

    from .forms import QuestionBankForm

    if request.method == 'POST':
        form = QuestionBankForm(request.POST)
        if form.is_valid():
            q = form.save(commit=False)
            q.created_by = request.user
            q.source = 'manual'
            q.save()
            messages.success(request, "✅ Question added.")
            if 'save_and_add' in request.POST:
                return redirect('academics:admin_question_create')
            return redirect('academics:admin_question_list')
        messages.error(request, "Please fix the errors below.")
    else:
        # Pre-select course if provided via ?course=<id>
        initial = {}
        course_id = request.GET.get('course')
        if course_id:
            initial['course'] = course_id
        form = QuestionBankForm(initial=initial)

    return render(request, 'academics/admin/cbt/question_form.html', {
        'form': form,
        'title': 'Add Question',
        'button_text': 'Save Question',
    })


@login_required
def admin_question_edit(request, pk):
    question = get_object_or_404(QuestionBank, pk=pk)
    if not request.user.has_perm('academics.change_questionbank'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_question_list')

    from .forms import QuestionBankForm

    if request.method == 'POST':
        form = QuestionBankForm(request.POST, instance=question)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Question updated.")
            return redirect('academics:admin_question_list')
        messages.error(request, "Please fix the errors below.")
    else:
        form = QuestionBankForm(instance=question)

    return render(request, 'academics/admin/cbt/question_form.html', {
        'form': form,
        'question': question,
        'title': 'Edit Question',
        'button_text': 'Save Changes',
    })


@require_POST
@login_required
def admin_question_delete(request, pk):
    question = get_object_or_404(QuestionBank, pk=pk)
    if not request.user.has_perm('academics.delete_questionbank'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_question_list')
    question.delete()
    messages.success(request, "🗑️ Question deleted.")
    return redirect('academics:admin_question_list')


@require_POST
@login_required
def admin_question_toggle(request, pk):
    question = get_object_or_404(QuestionBank, pk=pk)
    if not request.user.has_perm('academics.change_questionbank'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_question_list')
    question.is_active = not question.is_active
    question.save(update_fields=['is_active'])
    state = 'activated' if question.is_active else 'deactivated'
    messages.success(request, f"Question {state}.")
    return redirect('academics:admin_question_list')


@require_POST
@login_required
def admin_question_bulk_action(request):
    if not request.user.has_perm('academics.change_questionbank'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_question_list')

    action = request.POST.get('bulk_action', '')
    ids = request.POST.getlist('selected_ids')
    if not ids:
        messages.warning(request, "No questions selected.")
        return redirect('academics:admin_question_list')

    qs = QuestionBank.objects.filter(id__in=ids)

    if action == 'activate':
        n = qs.update(is_active=True)
        messages.success(request, f"✅ {n} question(s) activated.")
    elif action == 'deactivate':
        n = qs.update(is_active=False)
        messages.success(request, f"{n} question(s) deactivated.")
    elif action == 'mark_easy':
        n = qs.update(difficulty='easy')
        messages.success(request, f"{n} question(s) marked Easy.")
    elif action == 'mark_medium':
        n = qs.update(difficulty='medium')
        messages.success(request, f"{n} question(s) marked Medium.")
    elif action == 'mark_hard':
        n = qs.update(difficulty='hard')
        messages.success(request, f"{n} question(s) marked Hard.")
    elif action == 'delete' and request.user.has_perm('academics.delete_questionbank'):
        n, _ = qs.delete()
        messages.success(request, f"🗑️ {n} question(s) deleted.")
    else:
        messages.error(request, "Invalid action.")

    return redirect('academics:admin_question_list')


# ---------- Excel import / export ----------

EXCEL_HEADERS = [
    'Course', 'Topic', 'Difficulty', 'Question',
    'Option A', 'Option B', 'Option C', 'Option D',
    'Correct', 'Explanation',
]


@login_required
def admin_question_sample_template(request):
    """Download a blank Excel template with headers + one example row."""
    if not request.user.has_perm('academics.add_questionbank'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_question_list')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Questions'
    ws.append(EXCEL_HEADERS)
    ws.append([
        'Tajweed', 'Noon Sakinah', 'easy',
        'What is the ruling of Izhar?',
        'To make clear', 'To merge', 'To hide', 'To change',
        'A', 'Izhar means to make the letter clear.',
    ])
    # Column widths for readability
    widths = [18, 18, 12, 60, 25, 25, 25, 25, 10, 40]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=cbt_question_template.xlsx'
    wb.save(response)
    return response


@login_required
def admin_question_export(request):
    if not request.user.has_perm('academics.view_questionbank'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_question_list')

    qs = QuestionBank.objects.select_related('course').order_by('course__name', '-created_at')
    # Respect same filters as list view
    course_filter = request.GET.get('course', '')
    difficulty_filter = request.GET.get('difficulty', '')
    active_filter = request.GET.get('active', '')
    if course_filter:
        qs = qs.filter(course_id=course_filter)
    if difficulty_filter:
        qs = qs.filter(difficulty=difficulty_filter)
    if active_filter == 'yes':
        qs = qs.filter(is_active=True)
    elif active_filter == 'no':
        qs = qs.filter(is_active=False)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Questions'
    ws.append(EXCEL_HEADERS)
    for q in qs:
        ws.append([
            q.course.name, q.topic, q.difficulty, q.question_text,
            q.option_a, q.option_b, q.option_c, q.option_d,
            q.correct_option.upper(), q.explanation,
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"cbt_questions_{timezone.now():%Y%m%d_%H%M}.xlsx"
    response['Content-Disposition'] = f'attachment; filename={filename}'
    wb.save(response)
    return response


@login_required
def admin_question_import(request):
    if not request.user.has_perm('academics.add_questionbank'):
        messages.error(request, "Permission denied.")
        return redirect('academics:admin_question_list')

    errors = []
    created = 0
    skipped = 0

    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        create_missing_courses = request.POST.get('create_missing_courses') == 'on'

        if not excel_file:
            messages.error(request, "Please select an Excel file.")
        elif not excel_file.name.lower().endswith(('.xlsx', '.xls')):
            messages.error(request, "Only .xlsx or .xls files are supported.")
        else:
            try:
                wb = openpyxl.load_workbook(excel_file, data_only=True)
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))

                if not rows:
                    messages.error(request, "The file is empty.")
                else:
                    # Skip header row
                    for idx, row in enumerate(rows[1:], start=2):
                        if not row or not any(row):
                            continue

                        # Pad row to 10 columns
                        row = tuple(row) + (None,) * (10 - len(row))
                        (course_name, topic, difficulty, question_text,
                         opt_a, opt_b, opt_c, opt_d, correct, explanation) = row[:10]

                        # Normalize
                        course_name = (str(course_name).strip() if course_name else '')
                        topic = (str(topic).strip() if topic else '')
                        difficulty = (str(difficulty).strip().lower() if difficulty else 'medium')
                        question_text = (str(question_text).strip() if question_text else '')
                        opt_a = (str(opt_a).strip() if opt_a else '')
                        opt_b = (str(opt_b).strip() if opt_b else '')
                        opt_c = (str(opt_c).strip() if opt_c else '')
                        opt_d = (str(opt_d).strip() if opt_d else '')
                        correct = (str(correct).strip().lower() if correct else '')
                        explanation = (str(explanation).strip() if explanation else '')

                        # Validate required
                        if not course_name:
                            errors.append(f"Row {idx}: Course is required.")
                            skipped += 1
                            continue
                        if not question_text:
                            errors.append(f"Row {idx}: Question text is required.")
                            skipped += 1
                            continue
                        if not all([opt_a, opt_b, opt_c, opt_d]):
                            errors.append(f"Row {idx}: All 4 options are required.")
                            skipped += 1
                            continue
                        if correct not in ('a', 'b', 'c', 'd'):
                            errors.append(f"Row {idx}: Correct must be A, B, C, or D.")
                            skipped += 1
                            continue
                        if difficulty not in ('easy', 'medium', 'hard'):
                            errors.append(f"Row {idx}: Difficulty must be easy/medium/hard.")
                            skipped += 1
                            continue

                        # Find or create course
                        course = CBTCourse.objects.filter(name__iexact=course_name).first()
                        if not course:
                            if create_missing_courses:
                                course = CBTCourse.objects.create(
                                    name=course_name,
                                    slug=slugify(course_name)[:200] or 'course',
                                    created_by=request.user,
                                )
                            else:
                                errors.append(
                                    f"Row {idx}: Course '{course_name}' not found "
                                    f"(enable 'create missing' to auto-add)."
                                )
                                skipped += 1
                                continue

                        QuestionBank.objects.create(
                            course=course,
                            topic=topic,
                            difficulty=difficulty,
                            question_text=question_text,
                            option_a=opt_a, option_b=opt_b,
                            option_c=opt_c, option_d=opt_d,
                            correct_option=correct,
                            explanation=explanation,
                            source='excel',
                            created_by=request.user,
                        )
                        created += 1

                if created:
                    messages.success(request, f"✅ {created} question(s) imported.")
                if skipped:
                    messages.warning(request, f"⚠️ {skipped} row(s) skipped — see errors below.")
                if not created and not skipped:
                    messages.info(request, "No new questions were found in the file.")

                if created and not errors:
                    return redirect('academics:admin_question_list')

            except Exception as e:
                messages.error(request, f"Error reading file: {e}")

    return render(request, 'academics/admin/cbt/question_import.html', {
        'errors': errors[:50],   # cap to avoid flooding
        'created': created,
        'skipped': skipped,
    })


# ============================================================
# ==================== PUBLIC VIEWS =========================
# ============================================================

def cbt_home(request):
    """Public CBT landing page — or 'disabled' screen."""
    if not _cbt_enabled():
        return render(request, 'academics/cbt/disabled.html')

    courses = (
        CBTCourse.objects
        .filter(is_active=True)
        .annotate(q_total=Count('questions', filter=Q(questions__is_active=True)))
        .filter(q_total__gte=1)
        .order_by('order', 'name')
    )

    # Total active questions across all available courses
    total_questions = (
        QuestionBank.objects
        .filter(is_active=True, course__is_active=True)
        .count()
    )

    # Clear stale session state when landing on home
    _clear_cbt_session(request)

    return render(request, 'academics/cbt/home.html', {
        'courses': courses,
        'total_questions': total_questions,
        'settings': _site_settings(),
    })

def cbt_setup(request):
    """Student picks course + difficulty + question count."""
    if not _cbt_enabled():
        return render(request, 'academics/cbt/disabled.html')

    course_slug = request.GET.get('course', '')
    course = None
    if course_slug:
        course = CBTCourse.objects.filter(slug=course_slug, is_active=True).first()

    courses = (
        CBTCourse.objects
        .filter(is_active=True)
        .annotate(q_total=Count('questions', filter=Q(questions__is_active=True)))
        .filter(q_total__gte=1)
        .order_by('order', 'name')
    )

    if not courses.exists():
        return render(request, 'academics/cbt/setup.html', {
            'courses': courses,
            'course': course,
            'no_questions': True,
        })

    # Defaults
    default_count = course.get_default_question_count() if course else _cbt_default_count()
    default_minutes = course.get_default_time_minutes() if course else _cbt_default_minutes()

    context = {
        'courses': courses,
        'course': course,
        'default_count': default_count,
        'default_minutes': default_minutes,
        'min_questions': _cbt_min_questions(),
        'max_questions': _cbt_max_questions(),
        'allow_difficulty': _cbt_allow_difficulty(),
        'allow_topic': _cbt_allow_topic(),
        'no_questions': False,
    }
    return render(request, 'academics/cbt/setup.html', context)


@require_POST
def cbt_start(request):
    """Validate setup form, build a random test, store in session, show pre-test screen."""
    if not _cbt_enabled():
        return render(request, 'academics/cbt/disabled.html')

    # 1. Parse form
    course_slug = request.POST.get('course', '').strip()
    difficulty = request.POST.get('difficulty', 'mixed').strip().lower()
    topic = request.POST.get('topic', '').strip()
    student_name = request.POST.get('student_name', '').strip()
    student_email = request.POST.get('student_email', '').strip()

    try:
        num_questions = int(request.POST.get('num_questions', _cbt_default_count()))
    except (ValueError, TypeError):
        num_questions = _cbt_default_count()

    # 2. Validate
    course = CBTCourse.objects.filter(slug=course_slug, is_active=True).first()
    if not course:
        messages.error(request, "Please select a valid course.")
        return redirect('academics:cbt_setup')

    if not student_name:
        messages.error(request, "Please enter your name.")
        return redirect(f"{reverse('academics:cbt_setup')}?course={course.slug}")

    # Clamp count
    min_q = _cbt_min_questions()
    max_q = _cbt_max_questions()
    num_questions = max(min_q, min(max_q, num_questions))

    # Validate difficulty
    if difficulty not in ('easy', 'medium', 'hard', 'mixed'):
        difficulty = 'mixed'
    if not _cbt_allow_difficulty():
        difficulty = 'mixed'

    # Validate topic
    if topic and not _cbt_allow_topic():
        topic = ''

    # 3. Build pool + pick questions
    pool = _build_question_pool(course, difficulty=difficulty, topic=topic)
    if not pool:
        messages.error(request, "No questions available for that selection. Try different filters.")
        return redirect(f"{reverse('academics:cbt_setup')}?course={course.slug}")

    if len(pool) < num_questions:
        num_questions = len(pool)

    question_ids = _pick_random_questions(pool, num_questions)

    # 4. Time limit
    time_minutes = course.get_default_time_minutes()
    time_limit_seconds = time_minutes * 60

    # 5. Clear any prior state, then save new test to session
    _clear_cbt_session(request)

    request.session[CBT_TEST_KEY] = {
        'course_id': course.id,
        'course_slug': course.slug,
        'difficulty': difficulty,
        'topic': topic,
        'num_questions': num_questions,
        'time_limit_seconds': time_limit_seconds,
        'time_limit_minutes': time_minutes,
        'started_at': timezone.now().isoformat(),
        'question_ids': question_ids,
        'answers': {},
        'flagged': [],
        'tab_switches': 0,
        'warning_shown': False,
        'student_name': student_name,
        'student_email': student_email,
    }
    request.session.modified = True

    return redirect('academics:cbt_pretest')


def cbt_pretest(request):
    """Pre-test screen: verse + honesty reminder + Start button."""
    if not _cbt_enabled():
        return render(request, 'academics/cbt/disabled.html')

    test = _get_active_test(request)
    if not test:
        messages.info(request, "Please set up your test first.")
        return redirect('academics:cbt_setup')

    course = CBTCourse.objects.filter(id=test['course_id']).first()
    if not course:
        _clear_cbt_session(request)
        return redirect('academics:cbt_setup')

    settings_obj = _site_settings()

    return render(request, 'academics/cbt/pretest.html', {
        'test': test,
        'course': course,
        'verse': settings_obj.cbt_pre_test_verse if settings_obj else '',
        'message': settings_obj.cbt_pre_test_message if settings_obj else '',
        'tab_warning_threshold': _cbt_tab_switch_threshold(),
    })


def cbt_take(request):
    """Render the test page — all questions inline, JS handles navigation."""
    if not _cbt_enabled():
        return render(request, 'academics/cbt/disabled.html')

    test = _get_active_test(request)
    if not test:
        messages.info(request, "Please set up your test first.")
        return redirect('academics:cbt_setup')

    # Check expiry
    if _test_is_expired(test):
        messages.warning(request, "Time is up. Here's your result from what was saved.")
        return redirect('academics:cbt_submit')

    course = CBTCourse.objects.filter(id=test['course_id']).first()
    if not course:
        _clear_cbt_session(request)
        return redirect('academics:cbt_setup')

    # Fetch questions in the stored order
    qs = QuestionBank.objects.filter(id__in=test['question_ids'])
    q_map = {q.id: q for q in qs}
    ordered = [q_map[qid] for qid in test['question_ids'] if qid in q_map]

    # Build SAFE payload — never include correct_option
    payload = []
    for q in ordered:
        payload.append({
            'id': q.id,
            'text': q.question_text,
            'options': {
                'a': q.option_a,
                'b': q.option_b,
                'c': q.option_c,
                'd': q.option_d,
            },
            'difficulty': q.difficulty,
            'topic': q.topic,
            'saved_answer': test.get('answers', {}).get(str(q.id)),
            'flagged': q.id in test.get('flagged', []),
        })

    time_left = max(0, _test_time_left(test))

    return render(request, 'academics/cbt/take.html', {
        'test': test,
        'course': course,
        'questions_json': json.dumps(payload),
        'total_questions': len(payload),
        'time_left_seconds': time_left,
        'tab_warning_threshold': _cbt_tab_switch_threshold(),
    })


@require_POST
def cbt_submit(request):
    """Grade the test, save anonymous stats, store result in session, redirect."""
    if not _cbt_enabled():
        return render(request, 'academics/cbt/disabled.html')

    test = _get_active_test(request)
    if not test:
        messages.info(request, "No active test found.")
        return redirect('academics:cbt_home')

    # Check if way past grace — still grade but note the time
    expired = _test_is_expired(test)

    # 1. Parse answers from POST: answers[<qid>] = 'a'|'b'|'c'|'d'|''
    answers = {}
    for qid in test['question_ids']:
        raw = request.POST.get(f'answers[{qid}]', '').strip().lower()
        answers[str(qid)] = raw if raw in ('a', 'b', 'c', 'd') else None

    # 2. Grade
    result_core = _grade_test(test, answers)

    # 3. Update anonymous stats with F() expressions
    questions = {q.id: q for q in QuestionBank.objects.filter(id__in=test['question_ids'])}
    _increment_question_stats(test['question_ids'], answers, questions)

    # 4. Compute time taken
    time_taken = _test_seconds_elapsed(test)

    # 5. Fetch course info
    course = CBTCourse.objects.filter(id=test['course_id']).first()

    # 6. Store result in session (safe snapshot)
    request.session[CBT_RESULT_KEY] = {
        'course_id': test['course_id'],
        'course_name': course.name if course else '—',
        'course_slug': course.slug if course else '',
        'difficulty': test.get('difficulty', 'mixed'),
        'score': result_core['score'],
        'total': result_core['total'],
        'percentage': result_core['percentage'],
        'band': result_core['band'],
        'correct_ids': result_core['correct_ids'],
        'wrong_ids': result_core['wrong_ids'],
        'unanswered_ids': result_core['unanswered_ids'],
        'per_difficulty': result_core['per_difficulty'],
        'per_topic': result_core['per_topic'],
        'time_taken_seconds': time_taken,
        'time_limit_seconds': test.get('time_limit_seconds', 0),
        'student_name': test.get('student_name', ''),
        'student_email': test.get('student_email', ''),
        'expired': expired,
        'submitted_at': timezone.now().isoformat(),
    }
    request.session.modified = True

    # 7. Clear the test but keep the result
    request.session.pop(CBT_TEST_KEY, None)

    return redirect('academics:cbt_result')


def cbt_result(request):
    """Show score, breakdown, wrong-answer review, AI report."""
    if not _cbt_enabled():
        return render(request, 'academics/cbt/disabled.html')

    result = request.session.get(CBT_RESULT_KEY)
    if not result:
        messages.info(request, "No result found. Take a test first.")
        return redirect('academics:cbt_home')

    # Fetch question objects for the review (only if show_answers is on)
    show_answers = _cbt_show_answers()

    wrong_questions = []
    unanswered_questions = []
    if show_answers:
        # Preserve session order
        wrong_qs = {q.id: q for q in QuestionBank.objects.filter(id__in=result['wrong_ids'])}
        wrong_questions = [wrong_qs[qid] for qid in result['wrong_ids'] if qid in wrong_qs]

        unanswered_qs = {q.id: q for q in QuestionBank.objects.filter(id__in=result['unanswered_ids'])}
        unanswered_questions = [unanswered_qs[qid] for qid in result['unanswered_ids'] if qid in unanswered_qs]

    # Band metadata for template
    band_meta = {
        'excellent': {'label': 'Excellent', 'color': '#38a169', 'icon': '🌟',
                      'message': 'MashaAllah — outstanding work.'},
        'good':      {'label': 'Good', 'color': '#3182ce', 'icon': '👍',
                      'message': 'Well done — keep it up.'},
        'fair':      {'label': 'Fair', 'color': '#d69e2e', 'icon': '📘',
                      'message': "You're getting there — review and retake."},
        'needs_work':{'label': 'Needs Work', 'color': '#c0392b', 'icon': '💪',
                      'message': "Don't be discouraged — review the material."},
    }.get(result['band'], {'label': 'Result', 'color': '#C8A951', 'icon': '📋', 'message': ''})

    return render(request, 'academics/cbt/result.html', {
        'result': result,
        'band_meta': band_meta,
        'show_answers': show_answers,
        'wrong_questions': wrong_questions,
        'unanswered_questions': unanswered_questions,
        'ai_report_enabled': _cbt_ai_report_enabled(),
        'allow_retake': _cbt_allow_retake(),
    })


@require_POST
def cbt_ai_report(request):
    """AJAX endpoint — generates AI report from the current session result."""
    if not _cbt_enabled() or not _cbt_ai_report_enabled():
        return JsonResponse({'error': 'disabled'}, status=403)

    result = request.session.get(CBT_RESULT_KEY)
    if not result:
        return JsonResponse({'error': 'no_result'}, status=400)

    # --- Rate limit by IP (per hour) ---
    ip = (
        request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        or request.META.get('REMOTE_ADDR', '')
    )
    cache_key = f'cbt_ai_report:{ip}'
    count = cache.get(cache_key, 0)
    if count >= 15:
        return JsonResponse({
            'error': 'rate_limited',
            'message': "You've reached the AI report limit for now. Please try again later."
        }, status=429)
    cache.set(cache_key, count + 1, 3600)

    # --- Generate ---
    from .cbt_ai import generate_report
    try:
        text = generate_report(result)
    except Exception as e:
        return JsonResponse({
            'error': 'ai_failed',
            'message': 'AI report unavailable right now.',
            'fallback': _canned_report(result),
            'detail': str(e)[:200],
        }, status=200)

    return JsonResponse({
        'report': text,
        'cached': False,
    })


def _canned_report(result: dict) -> str:
    """Fallback message based on score band — used if AI fails or is disabled."""
    band = result.get('band', 'fair')
    name = result.get('student_name', '').strip().split(' ')[0] if result.get('student_name') else ''
    greeting = f"{name}, " if name else ''
    messages_map = {
        'excellent': "MashaAllah — excellent work. Keep up the consistency and aim higher.",
        'good': "Good effort. Review the topics you missed and try again to strengthen them.",
        'fair': "You're on the right track. Focus on the weak areas and retake the test.",
        'needs_work': "Don't be discouraged. Review the material carefully and try again — progress comes with patience.",
    }
    return greeting + messages_map.get(band, "Keep practicing — you'll improve.")


def cbt_retake(request):
    """Clear result and redirect to setup for a fresh test."""
    if not _cbt_enabled():
        return render(request, 'academics/cbt/disabled.html')
    request.session.pop(CBT_RESULT_KEY, None)
    request.session.pop(CBT_TEST_KEY, None)
    request.session.modified = True
    messages.success(request, "Fresh start — pick your course.")
    return redirect('academics:cbt_setup')


# ============================================================
# Tab-switch AJAX ping (optional, called from take.html JS)
# ============================================================

@require_POST
def cbt_tab_switch_ping(request):
    """Called by JS when the student switches tabs. Increments counter."""
    test = _get_active_test(request)
    if not test:
        return JsonResponse({'ok': False})
    try:
        data = json.loads(request.body or '{}')
        delta = int(data.get('delta', 1))
    except Exception:
        delta = 1
    test['tab_switches'] = test.get('tab_switches', 0) + delta
    request.session[CBT_TEST_KEY] = test
    request.session.modified = True
    return JsonResponse({
        'ok': True,
        'switches': test['tab_switches'],
        'threshold': _cbt_tab_switch_threshold(),
        'should_warn': (
            test['tab_switches'] >= _cbt_tab_switch_threshold()
            and not test.get('warning_shown')
        ),
    })