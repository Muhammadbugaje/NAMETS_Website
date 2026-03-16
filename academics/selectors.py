from django.utils import timezone
from .models import Course, Session, Material, Evaluation, Result
from django.db.models import Sum, Q

def get_active_courses(course_type=None):
    qs = Course.objects.filter(is_active=True)
    if course_type:
        qs = qs.filter(course_type=course_type)
    return qs

def get_course_by_slug(slug):
    return Course.objects.filter(slug=slug, is_active=True).first()

def get_upcoming_sessions(course=None):
    qs = Session.objects.filter(is_active=True, date__gte=timezone.now().date())
    if course:
        qs = qs.filter(course=course)
    return qs.order_by('date', 'start_time')

def get_course_materials(course):
    return Material.objects.filter(course=course, is_active=True)

def get_course_evaluations(course):
    return Evaluation.objects.filter(course=course, is_active=True)

def get_results_for_course(course, student_name=None):
    qs = Result.objects.filter(evaluation__course=course)
    if student_name:
        qs = qs.filter(student_name__icontains=student_name)
    return qs.select_related('evaluation')

def search_student_results(student_name):
    return Result.objects.filter(student_name__icontains=student_name).select_related('evaluation__course')

def get_student_summary(student_name):
    results = Result.objects.filter(student_name=student_name)
    total_marks = results.aggregate(total=Sum('marks_obtained'))['total']
    return {
        'results': results,
        'total': total_marks,
        'count': results.count(),
    }
        
def get_featured_materials(course):
    return Material.objects.filter(course=course, is_active=True, is_featured=True)

def get_featured_evaluations(course):
    return Evaluation.objects.filter(course=course, is_active=True, is_featured=True)
 
def get_upcoming_sessions(course_type=None):
    qs = Session.objects.filter(is_active=True, date__gte=timezone.now().date())
    if course_type:
        qs = qs.filter(course__course_type=course_type)
    return qs.order_by('date', 'start_time')  
 
def get_all_results(course_id=None, reg_no=None, student_name=None):
    from .models import Result
    qs = Result.objects.select_related('evaluation__course').all()
    if course_id:
        qs = qs.filter(evaluation__course_id=course_id)
    if reg_no:
        qs = qs.filter(registration_number__icontains=reg_no)
    if student_name:
        qs = qs.filter(student_name__icontains=student_name)
    return qs.order_by('student_name')   