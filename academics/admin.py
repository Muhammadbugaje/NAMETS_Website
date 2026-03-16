from django.contrib import admin
from .models import Course, Session, Material, Evaluation, Result, Tutor, TutorEvaluation
from django.http import HttpResponse
from django.urls import path, reverse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .forms import ExcelUploadForm
import openpyxl
from django.utils.html import format_html
from openpyxl.utils import get_column_letter
from datetime import datetime
from .models import TimetableEntry
from .views import upload_timetable_excel

# Register your models here.

# ResultInline must be defined before EvaluationAdmin
class ResultInline(admin.TabularInline):
    model = Result
    extra = 1
    readonly_fields = ('student_name', 'marks_obtained', 'grade')  # optional

# Define the view first
def upload_excel_view(request, evaluation_id):
    evaluation = get_object_or_404(Evaluation, id=evaluation_id)
    if request.method == 'POST':
        form = ExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['excel_file']
            wb = openpyxl.load_workbook(excel_file)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if len(rows) < 2:
                messages.error(request, "File is empty.")
                return redirect('admin:academics_evaluation_changelist')
            created_count = 0
            for row in rows[1:]:
                if not any(row):
                    continue
                # Expect: Student Name, Reg No, Marks, Grade, Remarks (optional)
                if len(row) < 4:
                    continue
                name = str(row[0]) if row[0] else ''
                reg_no = str(row[1]) if len(row) > 1 and row[1] else ''
                marks = row[2] if len(row) > 2 else 0
                grade = str(row[3]) if len(row) > 3 and row[3] else ''
                remarks = str(row[4]) if len(row) > 4 and row[4] else ''
                try:
                    marks = float(marks)
                except (ValueError, TypeError):
                    marks = 0.0
                Result.objects.create(
                    evaluation=evaluation,
                    student_name=name,
                    registration_number=reg_no,
                    marks_obtained=marks,
                    grade=grade,
                    remarks=remarks
                )
                created_count += 1
            messages.success(request, f"Successfully imported {created_count} results.")
            return redirect('admin:academics_evaluation_changelist')
    else:
        form = ExcelUploadForm()
    context = {
        'form': form,
        'evaluation': evaluation,
        'title': f"Upload results for {evaluation}",
    }
    return render(request, 'admin/academics/upload_excel.html', context)

@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'date', 'total_marks', 'upload_excel_button')
    list_filter = ('course', 'date')
    search_fields = ('title',)
    inlines = [ResultInline]

    def upload_excel_button(self, obj):
        url = reverse('admin:academics_evaluation_upload_excel', args=[obj.id])
        return format_html('<a class="button" href="{}">Upload Excel</a>', url)
    upload_excel_button.short_description = 'Upload Results'
    upload_excel_button.allow_tags = True

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:evaluation_id>/upload-excel/',
                 self.admin_site.admin_view(upload_excel_view),
                 name='academics_evaluation_upload_excel'),
        ]
        return custom_urls + urls

class SessionInline(admin.TabularInline):
    model = Session
    extra = 1

class MaterialInline(admin.TabularInline):
    model = Material
    extra = 1

class EvaluationInline(admin.TabularInline):
    model = Evaluation
    extra = 1

class ResultInline(admin.TabularInline):
    model = Result
    extra = 1
    readonly_fields = ('student_name', 'marks_obtained', 'grade')

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'course_type', 'is_active')
    list_filter = ('course_type', 'is_active')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    inlines = [SessionInline, MaterialInline, EvaluationInline]
    filter_horizontal = ('tutors',)  # or use a widget for ManyToMany

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('course', 'date', 'start_time', 'end_time', 'location')
    list_filter = ('course', 'date')
    search_fields = ('course__name',)

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'uploaded_at')
    list_filter = ('course',)
    search_fields = ('title',)

@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ('student_name', 'evaluation', 'marks_obtained', 'grade')
    list_filter = ('evaluation__course',)
    search_fields = ('student_name', 'student_email')
    actions = ['import_from_excel']  # We'll add this later
    
    
# tutors evaluation admin
@admin.register(Tutor)
class TutorAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)

@admin.register(TutorEvaluation)
class TutorEvaluationAdmin(admin.ModelAdmin):
    list_display = ('tutor', 'course', 'rating', 'student_name', 'submitted_at')
    list_filter = ('course', 'tutor', 'rating')
    search_fields = ('student_name', 'comments')
    actions = ['export_to_excel']

    def export_to_excel(self, request, queryset):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=tutor_evaluations_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Evaluations"

        headers = ['Course', 'Tutor', 'Student Name', 'Rating', 'Comments', 'Submitted At']
        for col_num, header in enumerate(headers, 1):
            col_letter = get_column_letter(col_num)
            ws[f'{col_letter}1'] = header
            ws[f'{col_letter}1'].font = openpyxl.styles.Font(bold=True)

        for row_num, obj in enumerate(queryset, 2):
            ws[f'A{row_num}'] = str(obj.course)
            ws[f'B{row_num}'] = obj.tutor.name
            ws[f'C{row_num}'] = obj.student_name
            ws[f'D{row_num}'] = obj.rating
            ws[f'E{row_num}'] = obj.comments
            ws[f'F{row_num}'] = obj.submitted_at.strftime("%Y-%m-%d %H:%M")

        wb.save(response)
        return response
    export_to_excel.short_description = "Export selected evaluations to Excel"

    
@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ('course_name', 'entry_type', 'day', 'time_start', 'time_end', 'venue', 'is_active')
    list_filter = ('entry_type', 'day', 'is_active')
    search_fields = ('course_name', 'venue')
    list_editable = ('is_active',)
    actions = ['export_selected']  # optional

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-excel/', self.admin_site.admin_view(upload_timetable_excel), name='academics_timetableentry_upload'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['upload_button'] = True
        return super().changelist_view(request, extra_context=extra_context)
    