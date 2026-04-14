from urllib import request
from django.shortcuts import render, get_object_or_404, redirect
from .models import Course, Evaluation, Material, TimetableEntry, UserResourceSubmission, IslamiyyaRegistration, TimetableEntry, CompetitionResult
from . import selectors
from .forms import TutorEvaluationForm, TimetableUploadForm, ResourceSubmissionForm, IslamiyyaRegistrationForm, CheckStatusForm
from django.contrib import messages
import openpyxl
from django.http import FileResponse, Http404, HttpResponse
import os
from datetime import datetime, timedelta
from .selectors import get_all_results
from cloudinary.utils import cloudinary_url
from core.models import SiteSettings
from .utils import render_to_pdf
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.db.models import Q
from django.core.paginator import Paginator

# Create your views here.

def course_list(request):
    tutorial_courses = selectors.get_active_courses(course_type='tutorial')
    islamiyya_courses = selectors.get_active_courses(course_type='islamiyya')
    tutorial_sessions = selectors.get_upcoming_sessions(course_type='tutorial')
    islamiyya_sessions = selectors.get_upcoming_sessions(course_type='islamiyya')

    # Combine and sort for unified timetable
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
    settings = SiteSettings.objects.first()   # add this
    context = {
        'course': course,
        'sessions': sessions,
        'materials': materials,
        'evaluations': evaluations,
        'settings': settings,
    }
    return render(request, 'academics/course_detail.html', context)

def course_results(request, slug):
    course = get_object_or_404(Course, slug=slug, is_active=True)
    student_name = request.GET.get('student', '')
    results = selectors.get_results_for_course(course, student_name)
    exam = get_object_or_404(Evaluation, course=course, is_active=True)
    context = {
        'course': course,
        'results': results,
        'student_name': student_name,
        'total_mark': exam.total_marks,
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
        'materials': materials
    })

def exam_list(request, slug=None):
    exams = Evaluation.objects.filter(is_active=True).select_related('course').order_by('-date')
    # Optional filtering by course
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
    timetable = TimetableEntry.objects.filter(entry_type='islamiyya', is_active=True).order_by('day', 'time_start')
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
    settings = SiteSettings.objects.first()
    if not settings or not settings.tutor_evaluations_open:
        # Show a closed page (reuse your existing template)
        return render(request, 'academics/evaluation_closed.html', {'type': 'tutor'})

    # ... rest of your view (existing code) ...
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
        'intro': settings.evaluation_intro_text,
    })

def download_material(request, material_id):
    material = get_object_or_404(Material, id=material_id, is_active=True)

    if material.file:
        # Generate a Cloudinary URL that forces download
        # Determine resource type: if it's an image, use 'image'; otherwise 'raw'
        # You can check the file extension or simply use 'raw' for all non-image files.
        # For simplicity, we'll use 'raw' for all files (works for PDFs, docs, etc.)
        options = {
            'resource_type': 'image',
            'flags': 'attachment',   # forces download
            # Optionally set a filename for the downloaded file
            # 'attachment_name': material.title + '.' + material.file.format
        }
        # The public_id is stored in the database; you can get it from material.file.public_id
        download_url, _ = cloudinary_url(material.file.public_id, **options)
        return redirect(download_url)

    elif material.drive_link:
        # Google Drive link – redirect as is
        return redirect(material.drive_link)

    else:
        raise Http404("No file attached to this material.")
    

def parse_time_range(time_range_str):
    """Convert '8-10' or '09:00-11:00' to (start_time, end_time)."""
    parts = time_range_str.replace(' ', '').split('-')
    if len(parts) != 2:
        raise ValueError("Invalid time range format (expected HH-HH or HH:MM-HH:MM)")
    start_str, end_str = parts
    # Add minutes if missing
    if ':' not in start_str:
        start_str += ':00'
    if ':' not in end_str:
        end_str += ':00'
    from datetime import datetime
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
            
            data_rows = rows[1:]  # skip header
            created_count = 0
            error_count = 0
            errors = []
            
            for idx, row in enumerate(data_rows, start=2):  # Excel row numbers
                if not any(row):
                    continue  # skip empty rows
                
                # Ensure at least 6 columns
                if len(row) < 6:
                    errors.append(f"Row {idx}: Not enough columns (found {len(row)}, need 6)")
                    continue
                
                day = row[0]
                time_range = row[1]
                course_name = row[2]
                venue = row[3]
                entry_type = row[4]
                level = row[5] if len(row) > 5 else 'level1'  # default to level1 if not provided
                
                # --- Validate day ---
                try:
                    day = int(day)
                    if day not in range(1, 8):
                        errors.append(f"Row {idx}: Day must be 1-7, got {day}")
                        continue
                except (ValueError, TypeError):
                    errors.append(f"Row {idx}: Invalid day value '{day}' (must be a number 1-7)")
                    continue
                
                # Parse time range
                try:
                    start, end = parse_time_range(str(time_range).strip())
                except ValueError as e:
                    errors.append(f"Row {idx}: {e}")
                    continue

                # Validate entry_type
                entry_type_clean = str(entry_type).strip().lower()
                if entry_type_clean not in ['tutorial', 'islamiyya']:
                    errors.append(f"Row {idx}: entry_type must be 'tutorial' or 'islamiyya'")
                    continue

                # Validate level
                level_clean = str(level).strip().lower()
                if level_clean not in ['level1', 'level2']:
                    errors.append(f"Row {idx}: level must be 'level1' or 'level2'")
                    continue
                            
                # --- Create entry ---
                TimetableEntry.objects.create(
                    day=day,
                    time_start=start,
                    time_end=end,
                    course_name=str(course_name).strip()[:200],
                    venue=str(venue).strip()[:200] if venue else '',
                    entry_type=entry_type_clean,
                    level=level_clean,
                    is_active=True
                )
                created_count += 1
            
            # Report results
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
    
    context = {
        'form': form,
        'title': 'Upload Timetable Excel',
    }
    return render(request, 'admin/academics/timetable_upload.html', context)



def islamiyya_registration_open(request):
    settings = SiteSettings.objects.first()
    return settings and settings.islamiyya_registration_open

def islamiyya_register(request):
    if not islamiyya_registration_open(request):
        return render(request, 'academics/islamiyya_registration_closed.html')

    if request.method == 'POST':
        form = IslamiyyaRegistrationForm(request.POST)
        if form.is_valid():
            registration = form.save()
            request.session['islamiyya_app_id'] = registration.application_id
            messages.success(request, 'Registration successful! You can now download your application slip from your dashboard.')
            return redirect('academics:islamiyya_dashboard')
    else:
        form = IslamiyyaRegistrationForm()
    return render(request, 'academics/islamiyya_register.html', {'form': form})

def islamiyya_check_status(request):
    if request.method == 'POST':
        form = CheckStatusForm(request.POST)
        if form.is_valid():
            identifier = form.cleaned_data['identifier']
            try:
                registration = IslamiyyaRegistration.objects.get(email=identifier)
            except IslamiyyaRegistration.DoesNotExist:
                try:
                    registration = IslamiyyaRegistration.objects.get(registration_number=identifier)
                except IslamiyyaRegistration.DoesNotExist:
                    registration = None
            if registration:
                # Store in session to allow download later
                request.session['islamiyya_app_id'] = registration.application_id
                return redirect('academics:islamiyya_dashboard')
            else:
                messages.error(request, 'No registration found with that email or registration number.')
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

    # Get global WhatsApp link from SiteSettings
    settings_obj = SiteSettings.objects.first()
    default_whatsapp = settings_obj.islamiyya_whatsapp_link if settings_obj else None

    if registration.is_verified:
        whatsapp_link = registration.whatsapp_link or default_whatsapp
        if registration.verified_at and registration.verified_at < timezone.now() - timedelta(days=365):
            whatsapp_link = None
            expired = True
        else:
            expired = False
    else:
        whatsapp_link = None
        expired = False

    return render(request, 'academics/islamiyya_dashboard.html', {
        'registration': registration,
        'whatsapp_link': whatsapp_link,
        'expired': expired,
    })

def islamiyya_download_slip(request):
    app_id = request.session.get('islamiyya_app_id')
    if not app_id:
        messages.error(request, 'Please check your status first.')
        return redirect('academics:islamiyya_check_status')
    registration = get_object_or_404(IslamiyyaRegistration, application_id=app_id)

    # Build absolute static URL for logos
    static_url = request.build_absolute_uri('/static/')
    pdf = render_to_pdf('academics/islamiyya_application_slip.html', {
        'registration': registration,
        'static_url': static_url,
    })
    if pdf:
        response = pdf
        response['Content-Disposition'] = f'attachment; filename="application_{registration.application_id}.pdf"'
        return response
    else:
        messages.error(request, 'Error generating PDF.')
        return redirect('academics:islamiyya_dashboard')
    

def resources_page(request):
    query = request.GET.get('q', '')
    resources = UserResourceSubmission.objects.filter(status='approved').order_by('-submitted_at')
    
    if query:
        resources = resources.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
    
    paginator = Paginator(resources, 12)  # 12 resources per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
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
    resource = get_object_or_404(UserResourceSubmission, pk=pk)
    resource.download_count += 1
    resource.save(update_fields=['download_count'])
    return redirect(resource.file.url)

def competition_results(request):
    # Start with all active results
    queryset = CompetitionResult.objects.filter(is_active=True)

    # Get filter parameters from request.GET
    selected_event = request.GET.get('event', '')
    selected_category = request.GET.get('category', '')
    selected_year = request.GET.get('year', '')

    # Apply filters
    if selected_event:
        queryset = queryset.filter(event_name=selected_event)
    if selected_category:
        queryset = queryset.filter(category=selected_category)
    if selected_year:
        queryset = queryset.filter(year=selected_year)

    # Ordering (already set in Meta)
    results = queryset

    # Get distinct values for filter dropdowns
    event_choices = CompetitionResult.objects.filter(is_active=True).values_list('event_name', flat=True).distinct().order_by('event_name')
    category_choices = CompetitionResult.objects.filter(is_active=True).values_list('category', flat=True).distinct().exclude(category='').order_by('category')
    year_choices = CompetitionResult.objects.filter(is_active=True).values_list('year', flat=True).distinct().exclude(year='').order_by('-year')  # newest first

    # Group results by "event_name – category" for display
    events = {}
    for r in results:
        key = f"{r.event_name} – {r.category}" if r.category else r.event_name
        events.setdefault(key, []).append(r)

    context = {
        'events': events,
        'event_choices': event_choices,
        'category_choices': category_choices,
        'year_choices': year_choices,
        'selected_event': selected_event,
        'selected_category': selected_category,
        'selected_year': selected_year,
    }
    return render(request, 'academics/competition_results.html', context)