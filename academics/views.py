from urllib import request
from django.shortcuts import render, get_object_or_404, redirect
from .models import Course, Evaluation, Material, TimetableEntry
from . import selectors
from .forms import TutorEvaluationForm, TimetableUploadForm
from django.contrib import messages
import openpyxl
from .models import TimetableEntry
from django.http import FileResponse, Http404
import os
from datetime import datetime

from .selectors import get_all_results
from .models import Course
from cloudinary.utils import cloudinary_url

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
    context = {
        'course': course,
        'sessions': sessions,
        'materials': materials,
        'evaluations': evaluations,
    }
    return render(request, 'academics/course_detail.html', context)

def course_results(request, slug):
    course = get_object_or_404(Course, slug=slug, is_active=True)
    student_name = request.GET.get('student', '')
    results = selectors.get_results_for_course(course, student_name)
    context = {
        'course': course,
        'results': results,
        'student_name': student_name,
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
    course_slug = slug or request.GET.get('course')
    if course_slug:
        exams = exams.filter(course__slug=course_slug)
    context = {
        'exams': exams,
        'courses': Course.objects.filter(is_active=True),
    }
    return render(request, 'academics/exams.html', context)

    
def tutorial_list(request):
    courses = selectors.get_active_courses(course_type='tutorial')  # keep courses if you still want them
    timetable = TimetableEntry.objects.filter(entry_type='tutorial', is_active=True).order_by('day', 'time_start')
    return render(request, 'academics/tutorial_list.html', {
        'courses': courses,
        'timetable': timetable,
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
    return render(request, 'academics/exams.html', context)


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
    return render(request, 'academics/evaluate_tutor.html', {'form': form, 'course': course})


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
                time_start = row[1]
                time_end = row[2]
                course_name = row[3]
                venue = row[4]
                entry_type = row[5]
                
                # --- Validate day ---
                try:
                    day = int(day)
                    if day not in range(1, 8):
                        errors.append(f"Row {idx}: Day must be 1-7, got {day}")
                        continue
                except (ValueError, TypeError):
                    errors.append(f"Row {idx}: Invalid day value '{day}' (must be a number 1-7)")
                    continue
                
                # --- Validate times (handle both HH:MM and HH:MM:SS) ---
                time_start_str = str(time_start).strip()
                time_end_str = str(time_end).strip()
                
                def parse_time(t_str):
                    # Try HH:MM first, then HH:MM:SS
                    for fmt in ('%H:%M', '%H:%M:%S'):
                        try:
                            return datetime.strptime(t_str, fmt).time()
                        except ValueError:
                            continue
                    raise ValueError(f"Invalid time format: '{t_str}'")
                
                try:
                    start = parse_time(time_start_str)
                    end = parse_time(time_end_str)
                except ValueError as e:
                    errors.append(f"Row {idx}: {e}")
                    continue
                
                # --- Validate entry type ---
                entry_type_clean = str(entry_type).strip().lower()
                if entry_type_clean not in ['tutorial', 'islamiyya']:
                    errors.append(f"Row {idx}: Entry type must be 'tutorial' or 'islamiyya', got '{entry_type}'")
                    continue
                
                # --- Create entry ---
                TimetableEntry.objects.create(
                    day=day,
                    time_start=start,
                    time_end=end,
                    course_name=str(course_name).strip()[:200],
                    venue=str(venue).strip()[:200] if venue else '',
                    entry_type=entry_type_clean,
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