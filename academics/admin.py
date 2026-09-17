# academics/admin.py — complete, updated for all models including CBT
from unfold.admin import ModelAdmin, TabularInline
from django.contrib import admin
from django.db.models import F
from django.http import HttpResponse
from django.urls import path, reverse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from django.utils.html import format_html, mark_safe
from datetime import datetime
import openpyxl
from openpyxl.styles import PatternFill, Font
from openpyxl.utils import get_column_letter

from core.email_utils import send_templated_email
from .forms import ExcelUploadForm
from .views import upload_timetable_excel
from .models import (
    Course, Session, Material, Evaluation, Result, Tutor, TutorEvaluation,
    IslamiyyaRegistration, IslamiyyaCourse, UserResourceSubmission,
    CompetitionResult, TimetableEntry,
    IslamiyyaSettings,
    AttendanceSession, AttendanceRecord,
    CBTCourse, QuestionBank,
)


# ============================================================
# RESULT INLINE (used by EvaluationAdmin)
# ============================================================

class ResultInline(TabularInline):
    model = Result
    extra = 1
    fields = ('student_name', 'registration_number', 'marks_obtained', 'grade', 'remarks')


# ============================================================
# UPLOAD EXCEL VIEW FOR EVALUATION
# ============================================================

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
                    remarks=remarks,
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


# ============================================================
# EVALUATION ADMIN
# ============================================================

@admin.register(Evaluation)
class EvaluationAdmin(ModelAdmin):
    list_display = ('title', 'course', 'date', 'total_marks', 'upload_excel_button')
    list_filter = ('course', 'date')
    search_fields = ('title',)
    inlines = [ResultInline]

    def upload_excel_button(self, obj):
        url = reverse('admin:academics_evaluation_upload_excel', args=[obj.id])
        return format_html('<a class="button" href="{}">Upload Excel</a>', url)
    upload_excel_button.short_description = 'Upload Results'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:evaluation_id>/upload-excel/',
                 self.admin_site.admin_view(upload_excel_view),
                 name='academics_evaluation_upload_excel'),
        ]
        return custom_urls + urls


# ============================================================
# COURSE ADMIN
# ============================================================

class SessionInline(TabularInline):
    model = Session
    extra = 1


class MaterialInline(TabularInline):
    model = Material
    extra = 1


class EvaluationInline(TabularInline):
    model = Evaluation
    extra = 1


@admin.register(Course)
class CourseAdmin(ModelAdmin):
    list_display = ('name', 'course_type', 'is_active')
    list_filter = ('course_type', 'is_active')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    inlines = [SessionInline, MaterialInline, EvaluationInline]
    filter_horizontal = ('tutors',)


# ============================================================
# SESSION / MATERIAL / RESULT
# ============================================================

@admin.register(Session)
class SessionAdmin(ModelAdmin):
    list_display = ('course', 'date', 'start_time', 'end_time', 'location')
    list_filter = ('course', 'date')
    search_fields = ('course__name',)


@admin.register(Material)
class MaterialAdmin(ModelAdmin):
    list_display = ('title', 'course', 'uploaded_at', 'is_active', 'is_featured')
    list_filter = ('course', 'is_active', 'is_featured')
    search_fields = ('title',)


@admin.register(Result)
class ResultAdmin(ModelAdmin):
    list_display = ('student_name', 'evaluation', 'marks_obtained', 'grade')
    list_filter = ('evaluation__course',)
    search_fields = ('student_name', 'student_email')


# ============================================================
# TUTOR ADMIN (expanded with new fields)
# ============================================================

@admin.register(Tutor)
class TutorAdmin(ModelAdmin):
    list_display = ('name', 'email', 'phone', 'is_active', 'teaches_islamiyya', 'teaches_tutorial')
    list_filter = ('is_active',)
    search_fields = ('name', 'email', 'phone')

    def teaches_islamiyya(self, obj):
        return obj.teaches_islamiyya
    teaches_islamiyya.boolean = True
    teaches_islamiyya.short_description = "Islamiyya"

    def teaches_tutorial(self, obj):
        return obj.teaches_tutorial
    teaches_tutorial.boolean = True
    teaches_tutorial.short_description = "Tutorial"


# ============================================================
# TUTOR EVALUATION ADMIN
# ============================================================

@admin.register(TutorEvaluation)
class TutorEvaluationAdmin(ModelAdmin):
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
            ws[f'{col_letter}1'].font = Font(bold=True)
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


# ============================================================
# TIMETABLE ADMIN
# ============================================================

@admin.register(TimetableEntry)
class TimetableEntryAdmin(ModelAdmin):
    list_display = ('course_name', 'entry_type', 'level', 'day', 'time_start', 'time_end', 'venue', 'is_active')
    list_filter = ('entry_type', 'level', 'day', 'is_active')
    search_fields = ('course_name', 'venue')
    list_editable = ('is_active',)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-excel/', self.admin_site.admin_view(upload_timetable_excel),
                 name='academics_timetableentry_upload'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['upload_button'] = True
        return super().changelist_view(request, extra_context=extra_context)


# ============================================================
# ISLAMIYYA COURSE ADMIN
# ============================================================

@admin.register(IslamiyyaCourse)
class IslamiyyaCourseAdmin(ModelAdmin):
    list_display = ('name', 'is_active')
    list_editable = ('is_active',)
    search_fields = ('name',)


# ============================================================
# ISLAMIYYA SETTINGS ADMIN
# ============================================================

@admin.register(IslamiyyaSettings)
class IslamiyyaSettingsAdmin(ModelAdmin):
    list_display = (
        'academic_session', 'registration_fee', 'account',
        'is_active', 'is_open', 'is_currently_open_display',
        'paid_count_display', 'pending_count_display', 'total_collected_display',
    )
    list_filter = ('is_active', 'is_open')
    search_fields = ('academic_session',)
    readonly_fields = ('created_at', 'updated_at', 'paid_count_display',
                       'pending_count_display', 'total_collected_display')
    fieldsets = (
        ('Session', {
            'fields': ('academic_session', 'is_active')
        }),
        ('Registration Window', {
            'fields': ('is_open', 'registration_opens_at', 'registration_closes_at')
        }),
        ('Payment', {
            'fields': ('registration_fee', 'account'),
            'description': 'All Islamiyya payments for this session will be recorded into the chosen bank account.'
        }),
        ('Student Communication', {
            'fields': ('whatsapp_group_link', 'instructions')
        }),
        ('Stats', {
            'fields': ('paid_count_display', 'pending_count_display', 'total_collected_display'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def is_currently_open_display(self, obj):
        if obj.is_currently_open:
            return format_html('<span style="color:#28a745; font-weight:600;">✓ Open</span>')
        return format_html('<span style="color:#dc3545; font-weight:600;">✗ Closed</span>')
    is_currently_open_display.short_description = "Currently"

    def paid_count_display(self, obj):
        return obj.paid_count
    paid_count_display.short_description = "Paid"

    def pending_count_display(self, obj):
        return obj.pending_count
    pending_count_display.short_description = "Pending"

    def total_collected_display(self, obj):
        return f"₦{obj.total_collected:,.2f}"
    total_collected_display.short_description = "Total Collected"


# ============================================================
# ISLAMIYYA REGISTRATION — BULK ACTIONS
# ============================================================

def mark_verified(modeladmin, request, queryset):
    """Mark as manually verified (mosque payment / cash / bank transfer)."""
    updated = 0
    for reg in queryset:
        if reg.payment_status != 'paid':
            fee = reg.session_settings.registration_fee if reg.session_settings else 0
            reg.payment_status = 'paid'
            reg.payment_method = 'manual'
            reg.amount_paid = fee
            reg.paid_at = timezone.now()
            reg.verified_by = request.user
            reg.verified_at = timezone.now()
            if reg.session_settings:
                reg.whatsapp_link = reg.session_settings.whatsapp_group_link or ''
            reg.save()
            updated += 1
    modeladmin.message_user(request, f"{updated} registration(s) marked as PAID (manual verification).")


def mark_unverified(modeladmin, request, queryset):
    """Revert to pending — clears payment + verification."""
    updated = 0
    for reg in queryset:
        if reg.payment_status in ('paid', 'waived'):
            reg.payment_status = 'pending'
            reg.payment_method = ''
            reg.amount_paid = 0
            reg.paid_at = None
            reg.verified_by = None
            reg.verified_at = None
            reg.whatsapp_link = ''
            reg.save()
            updated += 1
    modeladmin.message_user(request, f"{updated} registration(s) reverted to PENDING.")


def mark_refunded(modeladmin, request, queryset):
    """Mark as refunded (handled physically by EXCO)."""
    updated = 0
    for reg in queryset:
        if reg.payment_status == 'paid':
            reg.mark_refunded(by_user=request.user, note='Bulk refund')
            updated += 1
    modeladmin.message_user(request, f"{updated} registration(s) marked as REFUNDED.")


def mark_waived(modeladmin, request, queryset):
    """Waive the fee — student allowed in without payment."""
    updated = 0
    for reg in queryset:
        if reg.payment_status == 'pending':
            reg.mark_waived(by_user=request.user, note='Bulk waiver')
            updated += 1
    modeladmin.message_user(request, f"{updated} registration(s) marked as WAIVED.")


def issue_certificates(modeladmin, request, queryset):
    """Issue certificates for selected registrations."""
    issued = 0
    for reg in queryset:
        if reg.is_paid and not reg.certificate_issued:
            reg.issue_certificate(by_user=request.user)
            issued += 1
    modeladmin.message_user(request, f"{issued} certificate(s) issued.")


mark_verified.short_description = "Mark selected as PAID (Manual verification)"
mark_unverified.short_description = "Revert selected to PENDING"
mark_refunded.short_description = "Mark selected as REFUNDED"
mark_waived.short_description = "Mark selected as WAIVED"
issue_certificates.short_description = "Issue certificates for selected"


# ============================================================
# ISLAMIYYA EXPORT
# ============================================================

def export_islamiyya_registrations_to_excel(modeladmin, request, queryset):
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=islamiyya_registrations_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Islamiyya Registrations"

    gold_fill = PatternFill(start_color="C9A84C", end_color="C9A84C", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")

    headers = [
        'Application ID', 'Session', 'Name', 'Registration Number', 'Email', 'Phone',
        'Department', 'Gender', 'Level', 'Courses', 'Other Course',
        'Payment Status', 'Payment Method', 'Amount Paid', 'Paid At',
        'Verified By', 'Verified At', 'Certificate Number', 'Submitted At',
    ]
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.fill = gold_fill
        cell.font = header_font

    for row_num, obj in enumerate(queryset, 2):
        courses_str = ', '.join([c.name for c in obj.courses.all()])
        ws.cell(row=row_num, column=1, value=obj.application_id)
        ws.cell(row=row_num, column=2, value=obj.session_settings.academic_session if obj.session_settings else '')
        ws.cell(row=row_num, column=3, value=obj.name)
        ws.cell(row=row_num, column=4, value=obj.registration_number)
        ws.cell(row=row_num, column=5, value=obj.email)
        ws.cell(row=row_num, column=6, value=obj.phone)
        ws.cell(row=row_num, column=7, value=obj.department or '')
        ws.cell(row=row_num, column=8, value=obj.get_gender_display() if obj.gender else '')
        ws.cell(row=row_num, column=9, value=obj.get_level_display())
        ws.cell(row=row_num, column=10, value=courses_str)
        ws.cell(row=row_num, column=11, value=obj.other_course or '')
        ws.cell(row=row_num, column=12, value=obj.get_payment_status_display())
        ws.cell(row=row_num, column=13, value=obj.get_payment_method_display() if obj.payment_method else '')
        ws.cell(row=row_num, column=14, value=float(obj.amount_paid) if obj.amount_paid else 0)
        ws.cell(row=row_num, column=15, value=obj.paid_at.strftime('%Y-%m-%d %H:%M') if obj.paid_at else '')
        ws.cell(row=row_num, column=16, value=obj.verified_by.get_full_name() if obj.verified_by else '')
        ws.cell(row=row_num, column=17, value=obj.verified_at.strftime('%Y-%m-%d %H:%M') if obj.verified_at else '')
        ws.cell(row=row_num, column=18, value=obj.certificate_number or '')
        ws.cell(row=row_num, column=19, value=obj.submitted_at.strftime('%Y-%m-%d %H:%M'))

    wb.save(response)
    return response
export_islamiyya_registrations_to_excel.short_description = "Export selected to Excel"


# ============================================================
# ISLAMIYYA REGISTRATION ADMIN
# ============================================================

@admin.register(IslamiyyaRegistration)
class IslamiyyaRegistrationAdmin(ModelAdmin):
    list_display = (
        'application_id', 'name', 'email', 'level',
        'session_display', 'payment_status_display', 'amount_paid_display',
        'submitted_at',
    )
    list_filter = (
        'payment_status', 'payment_method', 'level',
        'session_settings', 'is_active',
    )
    search_fields = (
        'name', 'email', 'application_id', 'registration_number', 'phone',
    )
    actions = [
        mark_verified, mark_unverified, mark_refunded, mark_waived,
        issue_certificates, export_islamiyya_registrations_to_excel,
    ]
    filter_horizontal = ('courses',)
    readonly_fields = (
        'application_id', 'submitted_at', 'paid_at', 'verified_at',
        'refunded_at', 'certificate_issued_at', 'certificate_number',
    )
    fieldsets = (
        ('Identity', {
            'fields': ('application_id', 'session_settings', 'name', 'email',
                       'phone', 'gender', 'photo', 'department', 'registration_number')
        }),
        ('Academic', {
            'fields': ('level', 'courses', 'other_course')
        }),
        ('Payment', {
            'fields': ('payment_status', 'payment_method', 'amount_paid',
                       'payment_reference', 'paid_at')
        }),
        ('Verification', {
            'fields': ('verified_by', 'verified_at', 'whatsapp_link')
        }),
        ('Refund', {
            'fields': ('refunded_at', 'refunded_by', 'refund_note'),
            'classes': ('collapse',),
        }),
        ('Certificate', {
            'fields': ('certificate_issued', 'certificate_number',
                       'certificate_issued_at', 'certificate_issued_by'),
            'classes': ('collapse',),
        }),
        ('Meta', {
            'fields': ('is_active', 'notes'),
        }),
    )

    def session_display(self, obj):
        return obj.session_settings.academic_session if obj.session_settings else '—'
    session_display.short_description = "Session"

    def payment_status_display(self, obj):
        colors = {
            'paid': '#28a745',
            'waived': '#17a2b8',
            'refunded': '#dc3545',
            'pending': '#ffc107',
        }
        icons = {'paid': '✓', 'waived': '⊘', 'refunded': '↺', 'pending': '⏳'}
        color = colors.get(obj.payment_status, '#6c757d')
        icon = icons.get(obj.payment_status, '')
        return format_html(
            f'<span style="color:{color}; font-weight:600;">{icon} {obj.get_payment_status_display()}</span>'
        )
    payment_status_display.short_description = "Payment"

    def amount_paid_display(self, obj):
        return f"₦{obj.amount_paid:,.2f}"
    amount_paid_display.short_description = "Paid"


# ============================================================
# USER RESOURCE SUBMISSION ADMIN
# ============================================================

@admin.register(UserResourceSubmission)
class UserResourceSubmissionAdmin(ModelAdmin):
    list_display = ('title', 'submitted_by', 'email', 'status', 'submitted_at', 'download_link')
    list_filter = ('status', 'submitted_at')
    search_fields = ('title', 'description', 'submitted_by', 'email')
    readonly_fields = (
        'submitted_at', 'submitted_by', 'email', 'title', 'description',
        'file', 'download_link_in_form', 'reviewed_at', 'reviewed_by',
    )
    ordering = ('-submitted_at',)
    actions = ['approve_submissions', 'reject_submissions']

    def approve_submissions(self, request, queryset):
        approved = 0
        for obj in queryset:
            if obj.status != 'approved' and not obj.email_sent:
                obj.status = 'approved'
                obj.reviewed_at = timezone.now()
                obj.reviewed_by = request.user
                obj.save()
                submitter_name = obj.submitted_by or 'User'
                try:
                    send_templated_email(
                        subject="Your NAMETS resource has been approved",
                        recipients=[obj.email],
                        template_name='emails/resource_approved.html',
                        context={
                            'name': submitter_name,
                            'title': obj.title,
                            'resources_url': getattr(settings, 'SITE_URL', 'https://namets.org') + '/academics/resources/',
                        },
                    )
                    obj.email_sent = True
                    obj.save(update_fields=['email_sent'])
                except Exception:
                    pass
                approved += 1
        self.message_user(request, f"{approved} submission(s) approved.")
    approve_submissions.short_description = "Approve selected submissions"

    def reject_submissions(self, request, queryset):
        updated = queryset.update(status='rejected', reviewed_at=timezone.now(), reviewed_by=request.user)
        self.message_user(request, f"{updated} submission(s) rejected.")
    reject_submissions.short_description = "Reject selected submissions"

    def download_link(self, obj):
        if obj.file:
            file_url = obj.file.url if hasattr(obj.file, 'url') else obj.file
            return format_html('<a href="{}" target="_blank" class="button">📥 Download</a>', file_url)
        return "—"
    download_link.short_description = 'Download File'

    def download_link_in_form(self, obj):
        if obj.file:
            file_url = obj.file.url if hasattr(obj.file, 'url') else obj.file
            return format_html(
                '<a href="{}" target="_blank" class="button" style="background:#c9a84c; color:#1a1a1a; padding:5px 10px; border-radius:30px;">📥 Download File</a>',
                file_url
            )
        return "—"
    download_link_in_form.short_description = 'Download File'


# ============================================================
# COMPETITION RESULT ADMIN
# ============================================================

@admin.register(CompetitionResult)
class CompetitionResultAdmin(ModelAdmin):
    list_display = ('event_name', 'category', 'position', 'participant_name', 'department', 'points', 'order')
    list_filter = ('event_name', 'category', 'year')
    search_fields = ('participant_name', 'event_name')
    list_editable = ('order',)
    actions = ['export_to_excel']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-excel/', self.admin_site.admin_view(self.upload_excel),
                 name='academics_competitionresult_upload'),
        ]
        return custom_urls + urls

    def upload_excel(self, request):
        if request.method == 'POST':
            form = ExcelUploadForm(request.POST, request.FILES)
            if form.is_valid():
                excel_file = request.FILES['excel_file']
                wb = openpyxl.load_workbook(excel_file)
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))
                if len(rows) < 2:
                    messages.error(request, "File is empty or has only headers.")
                    return redirect('admin:academics_competitionresult_changelist')
                created_count = 0
                errors = []
                for idx, row in enumerate(rows[1:], start=2):
                    if not any(row):
                        continue
                    try:
                        event_name = str(row[0]).strip() if row[0] else ''
                        category = str(row[1]).strip() if row[1] else ''
                        position = str(row[2]).strip() if row[2] else ''
                        participant_name = str(row[3]).strip() if row[3] else ''
                        department = str(row[4]).strip() if row[4] else ''
                        points = row[5] if row[5] else None
                        year = str(row[6]).strip() if row[6] else ''
                        order = int(row[7]) if row[7] else 0
                    except Exception as e:
                        errors.append(f"Row {idx}: parsing error - {e}")
                        continue
                    if not event_name or not participant_name:
                        errors.append(f"Row {idx}: event_name and participant_name are required.")
                        continue
                    try:
                        points = float(points) if points else None
                    except Exception:
                        points = None
                    CompetitionResult.objects.create(
                        event_name=event_name,
                        category=category,
                        position=position,
                        participant_name=participant_name,
                        department=department,
                        points=points,
                        year=year,
                        order=order,
                        is_active=True,
                    )
                    created_count += 1
                if created_count:
                    messages.success(request, f"Successfully imported {created_count} competition results.")
                if errors:
                    for err in errors[:5]:
                        messages.error(request, err)
                    if len(errors) > 5:
                        messages.error(request, f"... and {len(errors)-5} more errors.")
                return redirect('admin:academics_competitionresult_changelist')
        else:
            form = ExcelUploadForm()
        return render(request, 'admin/academics/upload_excel.html', {
            'form': form,
            'title': 'Upload Competition Results Excel',
        })

    def export_to_excel(self, request, queryset):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=competition_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Competition Results"
        headers = ['Event Name', 'Category', 'Position', 'Participant Name', 'Department', 'Points', 'Year', 'Order']
        for col_num, header in enumerate(headers, 1):
            col_letter = get_column_letter(col_num)
            ws[f'{col_letter}1'] = header
            ws[f'{col_letter}1'].font = Font(bold=True)
        for row_num, obj in enumerate(queryset, 2):
            ws[f'A{row_num}'] = obj.event_name
            ws[f'B{row_num}'] = obj.category or ''
            ws[f'C{row_num}'] = obj.position
            ws[f'D{row_num}'] = obj.participant_name
            ws[f'E{row_num}'] = obj.department or ''
            ws[f'F{row_num}'] = obj.points if obj.points is not None else ''
            ws[f'G{row_num}'] = obj.year or ''
            ws[f'H{row_num}'] = obj.order
        wb.save(response)
        return response
    export_to_excel.short_description = "Export selected competition results to Excel"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['upload_button'] = True
        return super().changelist_view(request, extra_context=extra_context)


# ============================================================
# ATTENDANCE ADMIN
# ============================================================

class AttendanceRecordInline(TabularInline):
    model = AttendanceRecord
    extra = 0
    fields = ('user', 'islamiyya_registration', 'present', 'note')


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(ModelAdmin):
    list_display = (
        'title', 'session_type', 'date', 'course', 'islamiyya_settings',
        'taken_by', 'present_count_display', 'total_count_display',
    )
    list_filter = ('session_type', 'date', 'course')
    search_fields = ('title', 'course__name')
    readonly_fields = ('created_at', 'present_count_display', 'total_count_display')
    inlines = [AttendanceRecordInline]
    fieldsets = (
        ('Session', {
            'fields': ('session_type', 'title', 'date', 'taken_by')
        }),
        ('Linked Context', {
            'fields': ('course', 'islamiyya_settings'),
            'description': 'Set course for tutorials; set Islamiyya Settings for islamiyya class sessions.'
        }),
        ('Notes', {'fields': ('notes',)}),
        ('Stats', {
            'fields': ('present_count_display', 'total_count_display', 'created_at'),
            'classes': ('collapse',),
        }),
    )

    def present_count_display(self, obj):
        return obj.present_count
    present_count_display.short_description = "Present"

    def total_count_display(self, obj):
        return obj.total_count
    total_count_display.short_description = "Total"


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(ModelAdmin):
    list_display = ('session', 'who_display', 'present', 'note')
    list_filter = ('session__session_type', 'present', 'session__date')
    search_fields = ('user__first_name', 'user__last_name', 'islamiyya_registration__name')
    list_editable = ('present',)

    def who_display(self, obj):
        if obj.user:
            return obj.user.get_full_name() or obj.user.username
        if obj.islamiyya_registration:
            return obj.islamiyya_registration.name
        return '—'
    who_display.short_description = "Attendee"


# ============================================================
# CBT MODULE — Django Admin
# ============================================================

# ---------- Inline: questions inside a course ----------

class QuestionBankInline(TabularInline):
    """Compact preview of questions inside a CBT course page."""
    model = QuestionBank
    extra = 0
    fields = (
        'question_short', 'topic', 'difficulty',
        'correct_option', 'is_active', 'times_answered', 'correct_rate_display',
    )
    readonly_fields = (
        'question_short', 'correct_rate_display', 'times_answered',
    )
    show_change_link = True
    per_page = 15
    classes = ('collapse',)

    def question_short(self, obj):
        if not obj.pk:
            return '—'
        text = obj.question_text[:60]
        if len(obj.question_text) > 60:
            text += '…'
        return text
    question_short.short_description = 'Question'

    def correct_rate_display(self, obj):
        if not obj.pk:
            return '—'
        rate = obj.correct_rate
        if rate is None:
            return mark_safe('<span style="color:#999;">—</span>')
        color = '#38a169' if rate >= 70 else ('#d69e2e' if rate >= 40 else '#c0392b')
        return format_html(
            '<strong style="color:{};">{}%</strong>', color, rate
        )
    correct_rate_display.short_description = 'Correct %'

    def has_add_permission(self, request, obj=None):
        return False


# ---------- Custom filter: correct-rate bucket ----------

class CorrectRateFilter(admin.SimpleListFilter):
    title = 'correct rate'
    parameter_name = 'correct_rate'

    def lookups(self, request, model_admin):
        return [
            ('never', 'Never answered'),
            ('low', 'Low (< 40%) — possibly mis-keyed'),
            ('mid', 'Mid (40–69%)'),
            ('high', 'High (≥ 70%) — possibly too easy'),
        ]

    def queryset(self, request, queryset):
        v = self.value()
        if v == 'never':
            return queryset.filter(times_answered=0)
        if v == 'low':
            return queryset.filter(times_answered__gt=0).annotate(
                _rate=F('times_correct') * 100.0 / F('times_answered')
            ).filter(_rate__lt=40)
        if v == 'mid':
            return queryset.filter(times_answered__gt=0).annotate(
                _rate=F('times_correct') * 100.0 / F('times_answered')
            ).filter(_rate__gte=40, _rate__lt=70)
        if v == 'high':
            return queryset.filter(times_answered__gt=0).annotate(
                _rate=F('times_correct') * 100.0 / F('times_answered')
            ).filter(_rate__gte=70)
        return queryset


# ============================================================
# CBT COURSE ADMIN
# ============================================================

@admin.register(CBTCourse)
class CBTCourseAdmin(ModelAdmin):
    list_display = (
        'name_with_icon', 'slug', 'question_count_display',
        'difficulty_breakdown', 'is_active', 'order',
        'default_overrides', 'created_at',
    )
    list_display_links = ('name_with_icon',)
    list_filter = ('is_active',)
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('order', 'name')
    list_per_page = 30
    inlines = [QuestionBankInline]

    readonly_fields = (
        'created_at', 'updated_at',
        'question_count_display', 'difficulty_breakdown',
    )

    fieldsets = (
        ('Course Info', {
            'fields': ('name', 'slug', 'description', 'icon')
        }),
        ('Instructions for Students', {
            'fields': ('instructions',),
            'classes': ('collapse',),
        }),
        ('Display', {
            'fields': ('is_active', 'order')
        }),
        ('Per-course Overrides (leave blank to use global defaults)', {
            'fields': ('default_question_count', 'default_time_minutes'),
            'classes': ('collapse',),
        }),
        ('Statistics', {
            'fields': ('question_count_display', 'difficulty_breakdown'),
        }),
        ('Meta', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    actions = ['action_activate', 'action_deactivate']

    def name_with_icon(self, obj):
        return format_html(
            '<strong style="color:#0F3D2E;">{} {}</strong>',
            obj.icon or '📘', obj.name
        )
    name_with_icon.short_description = 'Course'
    name_with_icon.admin_order_field = 'name'

    def question_count_display(self, obj):
        if not obj.pk:
            return '—'
        total = obj.question_count()
        active = obj.questions.filter(is_active=True).count()
        color = '#38a169' if total >= 20 else ('#d69e2e' if total >= 10 else '#c0392b')
        return format_html(
            '<strong style="color:{};">{}</strong> '
            '<span style="color:#8a9b95;font-size:0.85em;">active</span>',
            color, active
        )
    question_count_display.short_description = 'Questions'

    def difficulty_breakdown(self, obj):
        if not obj.pk:
            return '—'
        e, m, h = obj.easy_count(), obj.medium_count(), obj.hard_count()
        return format_html(
            '<span style="background:#e8f2ec;color:#1a6b3c;padding:2px 8px;'
            'border-radius:10px;font-size:0.75em;font-weight:600;">E {}</span> '
            '<span style="background:#f5e9c8;color:#8a6a1a;padding:2px 8px;'
            'border-radius:10px;font-size:0.75em;font-weight:600;">M {}</span> '
            '<span style="background:#fdecea;color:#9b2c2c;padding:2px 8px;'
            'border-radius:10px;font-size:0.75em;font-weight:600;">H {}</span>',
            e, m, h
        )
    difficulty_breakdown.short_description = 'Difficulty'

    def default_overrides(self, obj):
        q = obj.default_question_count
        t = obj.default_time_minutes
        if not q and not t:
            return mark_safe('<span style="color:#8a9b95;">using global</span>')
        parts = []
        if q:
            parts.append(f"{q} Qs")
        if t:
            parts.append(f"{t} min")
        return ', '.join(parts)
    default_overrides.short_description = 'Overrides'

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description='Activate selected CBT courses')
    def action_activate(self, request, queryset):
        n = queryset.update(is_active=True)
        self.message_user(request, f"{n} course(s) activated.", messages.SUCCESS)

    @admin.action(description='Deactivate selected CBT courses')
    def action_deactivate(self, request, queryset):
        n = queryset.update(is_active=False)
        self.message_user(request, f"{n} course(s) deactivated.", messages.WARNING)


# ============================================================
# QUESTION BANK ADMIN
# ============================================================

@admin.register(QuestionBank)
class QuestionBankAdmin(ModelAdmin):
    list_display = (
        'question_preview', 'course', 'topic', 'difficulty_badge',
        'correct_option_display', 'is_active', 'source',
        'correct_rate_display', 'times_answered', 'created_at',
    )
    list_display_links = ('question_preview',)
    list_filter = (
        'course', 'difficulty', 'is_active', 'source', 'topic',
        CorrectRateFilter,
    )
    search_fields = (
        'question_text', 'topic',
        'option_a', 'option_b', 'option_c', 'option_d', 'explanation',
    )
    ordering = ('-created_at',)
    list_per_page = 50
    list_select_related = ('course', 'created_by')
    save_on_top = True
    date_hierarchy = 'created_at'

    readonly_fields = (
        'times_answered', 'times_correct', 'correct_rate_display',
        'created_at', 'updated_at',
    )

    fieldsets = (
        ('Classification', {
            'fields': ('course', 'topic', 'difficulty')
        }),
        ('Question Body', {
            'fields': ('question_text',),
        }),
        ('Options', {
            'fields': ('option_a', 'option_b', 'option_c', 'option_d'),
            'description': 'All four options are required. '
                           'The correct answer is selected below.',
        }),
        ('Answer', {
            'fields': ('correct_option', 'explanation'),
        }),
        ('Status', {
            'fields': ('is_active', 'source'),
        }),
        ('Statistics (anonymous aggregates)', {
            'fields': ('times_answered', 'times_correct', 'correct_rate_display'),
            'classes': ('collapse',),
        }),
        ('Meta', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    actions = [
        'action_activate', 'action_deactivate',
        'action_mark_easy', 'action_mark_medium', 'action_mark_hard',
        'action_reset_stats', 'action_duplicate',
    ]

    def question_preview(self, obj):
        text = obj.question_text[:75]
        if len(obj.question_text) > 75:
            text += '…'
        return format_html('<span style="color:#0F3D2E;">{}</span>', text)
    question_preview.short_description = 'Question'
    question_preview.admin_order_field = 'created_at'

    def difficulty_badge(self, obj):
        colors = {
            'easy':   ('#e8f2ec', '#1a6b3c', 'Easy'),
            'medium': ('#f5e9c8', '#8a6a1a', 'Medium'),
            'hard':   ('#fdecea', '#9b2c2c', 'Hard'),
        }
        bg, fg, label = colors.get(obj.difficulty, ('#eee', '#333', obj.difficulty))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;'
            'border-radius:10px;font-size:0.72em;font-weight:700;">{}</span>',
            bg, fg, label
        )
    difficulty_badge.short_description = 'Difficulty'
    difficulty_badge.admin_order_field = 'difficulty'

    def correct_option_display(self, obj):
        return format_html(
            '<strong style="color:#0F3D2E;">{}</strong>',
            obj.correct_option.upper()
        )
    correct_option_display.short_description = 'Answer'
    correct_option_display.admin_order_field = 'correct_option'

    def correct_rate_display(self, obj):
        rate = obj.correct_rate
        if rate is None:
            return mark_safe('<span style="color:#8a9b95;">—</span>')
        color = '#38a169' if rate >= 70 else ('#d69e2e' if rate >= 40 else '#c0392b')
        return format_html(
            '<strong style="color:{};">{}%</strong>', color, rate
        )
    correct_rate_display.short_description = 'Correct %'

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description='Activate selected questions')
    def action_activate(self, request, queryset):
        n = queryset.update(is_active=True)
        self.message_user(request, f"{n} question(s) activated.", messages.SUCCESS)

    @admin.action(description='Deactivate selected questions')
    def action_deactivate(self, request, queryset):
        n = queryset.update(is_active=False)
        self.message_user(request, f"{n} question(s) deactivated.", messages.WARNING)

    @admin.action(description='Mark as Easy')
    def action_mark_easy(self, request, queryset):
        n = queryset.update(difficulty='easy')
        self.message_user(request, f"{n} question(s) marked Easy.", messages.SUCCESS)

    @admin.action(description='Mark as Medium')
    def action_mark_medium(self, request, queryset):
        n = queryset.update(difficulty='medium')
        self.message_user(request, f"{n} question(s) marked Medium.", messages.SUCCESS)

    @admin.action(description='Mark as Hard')
    def action_mark_hard(self, request, queryset):
        n = queryset.update(difficulty='hard')
        self.message_user(request, f"{n} question(s) marked Hard.", messages.SUCCESS)

    @admin.action(description='Reset stats (times_answered / times_correct)')
    def action_reset_stats(self, request, queryset):
        n = queryset.update(times_answered=0, times_correct=0)
        self.message_user(request, f"Stats reset for {n} question(s).", messages.WARNING)

    @admin.action(description='Duplicate selected questions')
    def action_duplicate(self, request, queryset):
        created = 0
        for q in queryset:
            q.pk = None
            q.question_text = f"{q.question_text} (copy)"
            q.times_answered = 0
            q.times_correct = 0
            q.created_by = request.user
            q.save()
            created += 1
        self.message_user(request, f"{created} question(s) duplicated.", messages.SUCCESS)
    
    
    
    
from django.contrib import admin
from django.utils.html import format_html
from .models import Book, BookCategory


@admin.register(BookCategory)
class BookCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'icon', 'book_count_display', 'color_swatch')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('order', 'name')
    search_fields = ('name',)

    @admin.display(description='Books')
    def book_count_display(self, obj):
        return obj.book_count

    @admin.display(description='Color')
    def color_swatch(self, obj):
        return format_html(
            '<span style="display:inline-block;width:22px;height:22px;'
            'border-radius:6px;border:1px solid #ccc;background:{}"></span>',
            obj.color or '#0F3D2E'
        )


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'author', 'category',
        'is_featured', 'is_published', 'uploaded_at_display',
    )
    list_filter = ('category', 'is_featured', 'is_published', 'language')
    search_fields = ('title', 'author', 'isbn', 'publisher', 'external_file_url')
    list_editable = ('is_featured', 'is_published')
    raw_id_fields = ('uploaded_by',)
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='Uploaded')
    def uploaded_at_display(self, obj):
        return obj.created_at.strftime('%b %d, %Y') if obj.created_at else '—'

    fieldsets = (
        ('Basic info', {
            'fields': ('title', 'description', 'category'),
        }),
        ('Book details', {
            'fields': (
                'author', 'isbn', 'publisher', 'publication_year',
                'edition', 'pages', 'language',
            ),
        }),
        ('Cover', {
            'fields': ('cover_image', 'external_cover_url'),
            'description': 'Uploaded image takes priority over external URL.',
        }),
        ('Book file', {
            'fields': ('file', 'external_file_url', 'external_file_label'),
            'description': (
                'Upload a file, or paste an external link (Google Drive, etc). '
                'External link takes priority if both are provided.'
            ),
        }),
        ('Flags & ordering', {
            'fields': ('is_featured', 'is_published', 'order', 'uploaded_by'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    
from django.contrib import admin
from django.utils.html import format_html
from .models import CBTViolation


@admin.register(CBTViolation)
class CBTViolationAdmin(admin.ModelAdmin):
    list_display = (
        'occurred_at', 'user_display', 'violation_display',
        'course', 'attempt_id_short', 'triggered_submit',
    )
    list_filter = ('violation_type', 'triggered_submit', 'occurred_at', 'course')
    search_fields = ('attempt_id', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('occurred_at',)
    raw_id_fields = ('user', 'course')
    date_hierarchy = 'occurred_at'

    @admin.display(description='User')
    def user_display(self, obj):
        if not obj.user:
            return '—'
        return obj.user.get_full_name() or obj.user.email

    @admin.display(description='Violation')
    def violation_display(self, obj):
        return format_html(
            '<i class="fas {}" style="color:#C8A951;margin-right:4px;"></i> {}',
            obj.type_icon,
            obj.get_violation_type_display(),
        )

    @admin.display(description='Attempt')
    def attempt_id_short(self, obj):
        return obj.attempt_id[:10] + '…' if len(obj.attempt_id) > 10 else obj.attempt_id    
    
    
    