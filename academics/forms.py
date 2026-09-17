from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import (
    Tutor, Course, Session, Material, Evaluation, Result,
    TutorEvaluation, TimetableEntry, IslamiyyaCourse,
    IslamiyyaSettings, IslamiyyaRegistration,
    UserResourceSubmission, CompetitionResult,
    AttendanceSession, AttendanceRecord,
)
import os


# ============================================================
# EXISTING PUBLIC FORMS (unchanged)
# ============================================================

class ExcelUploadForm(forms.Form):
    excel_file = forms.FileField(
        label="Select Excel file",
        help_text="First row should be headers. Columns: Student Name, Registration Number, Marks Obtained, Grade, Remarks (optional).",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx,.xls'}),
    )


class TutorEvaluationForm(forms.ModelForm):
    class Meta:
        model = TutorEvaluation
        fields = ['tutor', 'student_name', 'rating', 'comments']
        widgets = {
            'rating': forms.RadioSelect(choices=TutorEvaluation.RATING_CHOICES),
            'comments': forms.Textarea(attrs={'rows': 4}),
        }
        labels = {
            'tutor': 'Select Tutor',
            'student_name': 'Your Name (optional)',
            'rating': 'Rating',
            'comments': 'Additional Comments (optional)',
        }

    def __init__(self, *args, **kwargs):
        course = kwargs.pop('course', None)
        super().__init__(*args, **kwargs)
        if course:
            self.fields['tutor'].queryset = course.tutors.filter(is_active=True)


class TimetableUploadForm(forms.Form):
    excel_file = forms.FileField(
        label="Select Excel file",
        help_text="Columns: Day (1-7), Time Range (e.g. 8-10), Course Name, Venue, Entry Type (tutorial/islamiyya), Level (level1/level2).",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx,.xls'}),
    )


class IslamiyyaRegistrationForm(forms.ModelForm):
    class Meta:
        model = IslamiyyaRegistration
        fields = ['name', 'email', 'gender', 'photo', 'phone', 'department',
                  'registration_number', 'level', 'courses', 'other_course']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your@email.com'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'photo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '08012345678'}),
            'department': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Mechanical Engineering'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. U22EE1001'}),
            'level': forms.Select(attrs={'class': 'form-control'}),
            'courses': forms.CheckboxSelectMultiple(),
            'other_course': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'If other, specify course'}),
        }
        labels = {
            'name': 'Full Name',
            'email': 'Email Address',
            'gender': 'Gender',
            'photo': 'Photo',
            'phone': 'Phone Number',
            'department': 'Department',
            'registration_number': 'Registration Number / Student ID',
            'level': 'Level',
            'courses': 'Select Courses',
            'other_course': 'Other Course',
        }

    def clean(self):
        cleaned_data = super().clean()
        courses = cleaned_data.get('courses')
        other = cleaned_data.get('other_course')
        if not courses and not other:
            self.add_error('courses', 'Please select at least one course or specify an "other" course.')
        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and IslamiyyaRegistration.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                "An application with this email already exists. Please check your status."
            )
        return email


class CheckStatusForm(forms.Form):
    identifier = forms.CharField(
        label="Email, Registration Number, or Application ID",
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'your@email.com / U22EE1001 / ISL-2025-0001',
        }),
    )


class ResourceSubmissionForm(forms.ModelForm):
    class Meta:
        model = UserResourceSubmission
        fields = ['title', 'description', 'file', 'submitted_by', 'email']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Resource title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Describe the resource...'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'submitted_by': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your name (optional)'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Your email (to receive approval notification)'}),
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if file.size > 10 * 1024 * 1024:
                raise ValidationError("File too large. Maximum size is 10MB.")
            ext = os.path.splitext(file.name)[1].lower().replace('.', '')
            allowed = ['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'zip', 'pptx', 'xlsx', 'txt']
            if ext not in allowed:
                raise ValidationError(
                    f'Unsupported file type: .{ext}. Allowed: {", ".join(allowed)}'
                )
        return file


# ============================================================
# EXCO ADMIN — TUTOR
# ============================================================

class TutorForm(forms.ModelForm):
    class Meta:
        model = Tutor
        fields = ['name', 'email', 'phone', 'bio', 'photo', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'photo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'Full Name',
            'email': 'Email Address',
            'phone': 'Phone Number',
            'bio': 'Short Bio',
            'photo': 'Photo',
            'is_active': 'Active',
        }


# ============================================================
# EXCO ADMIN — COURSE
# ============================================================

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['name', 'slug', 'description', 'course_type', 'tutors', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'auto-generated-from-name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'course_type': forms.Select(attrs={'class': 'form-control'}),
            'tutors': forms.SelectMultiple(attrs={'class': 'form-control', 'size': 6}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'Course Name',
            'slug': 'URL Slug',
            'description': 'Description',
            'course_type': 'Type',
            'tutors': 'Tutors',
            'is_active': 'Active',
        }
        help_texts = {
            'slug': 'Used in URLs. Auto-fill from name if left blank.',
            'tutors': 'Hold Ctrl/Cmd to select multiple tutors.',
        }

    def clean_slug(self):
        slug = self.cleaned_data.get('slug', '').strip()
        if not slug:
            from django.utils.text import slugify
            slug = slugify(self.cleaned_data.get('name', ''))
        return slug


# ============================================================
# EXCO ADMIN — SESSION
# ============================================================

class SessionForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ['course', 'title', 'date', 'start_time', 'end_time', 'location', 'is_active']
        widgets = {
            'course': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'course': 'Course',
            'title': 'Session Title',
            'date': 'Date',
            'start_time': 'Start Time',
            'end_time': 'End Time',
            'location': 'Location',
            'is_active': 'Active',
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_time')
        end = cleaned.get('end_time')
        if start and end and end <= start:
            self.add_error('end_time', 'End time must be after start time.')
        return cleaned


# ============================================================
# EXCO ADMIN — MATERIAL
# ============================================================

class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['course', 'title', 'description', 'file', 'drive_link', 'is_active', 'is_featured']
        widgets = {
            'course': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'drive_link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://drive.google.com/...'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'course': 'Course',
            'title': 'Title',
            'description': 'Description',
            'file': 'File Upload',
            'drive_link': 'Google Drive Link',
            'is_active': 'Active',
            'is_featured': 'Featured on Course Page',
        }
        help_texts = {
            'drive_link': 'Optional — used if no file is uploaded.',
        }

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('file') and not cleaned.get('drive_link'):
            raise ValidationError("Please upload a file or provide a Google Drive link.")
        return cleaned


# ============================================================
# EXCO ADMIN — EVALUATION (EXAM)
# ============================================================

class EvaluationForm(forms.ModelForm):
    class Meta:
        model = Evaluation
        fields = ['course', 'title', 'description', 'date', 'total_marks', 'is_active', 'is_featured']
        widgets = {
            'course': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'total_marks': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# ============================================================
# EXCO ADMIN — TIMETABLE
# ============================================================

class TimetableForm(forms.ModelForm):
    class Meta:
        model = TimetableEntry
        fields = ['day', 'time_start', 'time_end', 'course_name', 'venue',
                  'entry_type', 'level', 'order', 'is_active']
        widgets = {
            'day': forms.Select(attrs={'class': 'form-control'}),
            'time_start': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'time_end': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'course_name': forms.TextInput(attrs={'class': 'form-control'}),
            'venue': forms.TextInput(attrs={'class': 'form-control'}),
            'entry_type': forms.Select(attrs={'class': 'form-control'}),
            'level': forms.Select(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('time_start')
        end = cleaned.get('time_end')
        if start and end and end <= start:
            self.add_error('time_end', 'End time must be after start time.')
        return cleaned


# ============================================================
# EXCO ADMIN — ISLAMIYYA COURSE
# ============================================================

class IslamiyyaCourseForm(forms.ModelForm):
    class Meta:
        model = IslamiyyaCourse
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# ============================================================
# EXCO ADMIN — ISLAMIYYA SETTINGS
# ============================================================

class IslamiyyaSettingsForm(forms.ModelForm):
    class Meta:
        model = IslamiyyaSettings
        fields = ['academic_session', 'registration_fee', 'account',
                  'whatsapp_group_link', 'instructions',
                  'is_open', 'registration_opens_at', 'registration_closes_at',
                  'is_active']
        widgets = {
            'academic_session': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2025/2026'}),
            'registration_fee': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'account': forms.Select(attrs={'class': 'form-control'}),
            'whatsapp_group_link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://chat.whatsapp.com/...'}),
            'instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'is_open': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'registration_opens_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'registration_closes_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'academic_session': 'Academic Session',
            'registration_fee': 'Registration Fee (₦)',
            'account': 'Receiving Bank Account',
            'whatsapp_group_link': 'WhatsApp Group Link',
            'instructions': 'Instructions (shown on registration page)',
            'is_open': 'Registration Open',
            'registration_opens_at': 'Auto-Open At (optional)',
            'registration_closes_at': 'Auto-Close At (optional)',
            'is_active': 'This is the current active session',
        }
        help_texts = {
            'account': 'All payments for this session land in this bank account.',
            'registration_fee': 'Fixed fee. Every student must pay this exact amount.',
            'whatsapp_group_link': 'Revealed to students after payment is verified.',
            'is_active': 'Only one session can be active. Activating this one will deactivate the others.',
            'registration_opens_at': 'Leave blank to open immediately when "Registration Open" is checked.',
            'registration_closes_at': 'Leave blank to never auto-close.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from business.models import BankAccount
        self.fields['account'].queryset = BankAccount.objects.filter(is_active=True)
        self.fields['account'].empty_label = "— Select Account —"
        self.fields['registration_opens_at'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['registration_closes_at'].input_formats = ['%Y-%m-%dT%H:%M']

    def clean(self):
        cleaned = super().clean()
        opens = cleaned.get('registration_opens_at')
        closes = cleaned.get('registration_closes_at')
        if opens and closes and closes <= opens:
            self.add_error('registration_closes_at', 'Close time must be after open time.')

        fee = cleaned.get('registration_fee')
        account = cleaned.get('account')
        if fee and fee > 0 and not account:
            self.add_error('account',
                'A bank account must be selected when the fee is greater than zero '
                '(otherwise no payment can be recorded).')
        return cleaned


# ============================================================
# EXCO ADMIN — ISLAMIYYA REGISTRATION
# ============================================================

class IslamiyyaRegistrationAdminForm(forms.ModelForm):
    class Meta:
        model = IslamiyyaRegistration
        fields = [
            'session_settings', 'name', 'email', 'gender', 'photo',
            'department', 'phone', 'registration_number', 'level',
            'courses', 'other_course',
            'payment_status', 'payment_method', 'amount_paid',
            'payment_reference', 'notes', 'is_active',
        ]
        widgets = {
            'session_settings': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'photo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'level': forms.Select(attrs={'class': 'form-control'}),
            'courses': forms.SelectMultiple(attrs={'class': 'form-control', 'size': 6}),
            'other_course': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_status': forms.Select(attrs={'class': 'form-control'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'amount_paid': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'payment_reference': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'session_settings': 'Session',
            'registration_number': 'Registration Number',
            'courses': 'Courses',
            'other_course': 'Other Course',
            'payment_status': 'Payment Status',
            'payment_method': 'Payment Method',
            'amount_paid': 'Amount Paid (₦)',
            'payment_reference': 'Payment Reference',
            'notes': 'EXCO Internal Notes',
            'is_active': 'Enrollment Active',
        }
        help_texts = {
            'payment_status': 'Change to "Paid" to manually verify a mosque/cash payment.',
            'amount_paid': 'Defaults to the session fee. Adjust only if the amount was different.',
        }


# ============================================================
# EXCO ADMIN — COMPETITION RESULT
# ============================================================

class CompetitionResultForm(forms.ModelForm):
    class Meta:
        model = CompetitionResult
        fields = ['event_name', 'category', 'position', 'participant_name',
                  'department', 'points', 'year', 'order', 'is_active']
        widgets = {
            'event_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. NAMETS Week 2025'}),
            'category': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Quiz Competition'}),
            'position': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 1st / 2nd / participant'}),
            'participant_name': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'points': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'year': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2025/2026'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'event_name': 'Event Name',
            'category': 'Category',
            'position': 'Position',
            'participant_name': 'Participant Name',
            'department': 'Department',
            'points': 'Points',
            'year': 'Academic Year',
            'order': 'Display Order',
            'is_active': 'Active',
        }


# ============================================================
# EXCO ADMIN — ATTENDANCE
# ============================================================

class AttendanceSessionForm(forms.ModelForm):
    class Meta:
        model = AttendanceSession
        fields = ['session_type', 'course', 'islamiyya_settings', 'title', 'date', 'notes']
        widgets = {
            'session_type': forms.Select(attrs={'class': 'form-control', 'id': 'id_session_type'}),
            'course': forms.Select(attrs={'class': 'form-control', 'id': 'id_course'}),
            'islamiyya_settings': forms.Select(attrs={'class': 'form-control', 'id': 'id_islamiyya_settings'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'session_type': 'Session Type',
            'course': 'Course (for Tutorial sessions)',
            'islamiyya_settings': 'Islamiyya Session',
            'title': 'Session Title',
            'date': 'Date',
            'notes': 'Notes',
        }
        help_texts = {
            'course': 'Only applies to Tutorial sessions.',
            'islamiyya_settings': 'Only applies to Islamiyyah sessions.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['course'].queryset = Course.objects.filter(is_active=True)
        self.fields['course'].empty_label = "— None —"
        self.fields['islamiyya_settings'].queryset = IslamiyyaSettings.objects.all().order_by('-academic_session')
        self.fields['islamiyya_settings'].empty_label = "— None —"
        self.fields['course'].required = False
        self.fields['islamiyya_settings'].required = False
        
        
class ResultForm(forms.ModelForm):
    class Meta:
        model = Result
        fields = ['student_name', 'registration_number', 'student_email',
                  'marks_obtained', 'grade', 'remarks']
        widgets = {
            'student_name': forms.TextInput(attrs={'class': 'form-control'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'student_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'marks_obtained': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'grade': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'A / B+ / C'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }        
        
        
        
# ============================================================
# CBT FORMS
# ============================================================

from .models import CBTCourse, QuestionBank 


class CBTCourseForm(forms.ModelForm):
    """Form for creating/editing a CBT course."""

    class Meta:
        model = CBTCourse
        fields = [
            'name', 'slug', 'description', 'instructions',
            'icon', 'is_active', 'order',
            'default_question_count', 'default_time_minutes',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Tajweed Level 1',
                'required': True,
            }),
            'slug': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'auto-generated if left blank',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Short description shown to students.',
            }),
            'instructions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional instructions shown above the test for this course only.',
            }),
            'icon': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '📘',
                'maxlength': 10,
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
            }),
            'default_question_count': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': 'Global default',
            }),
            'default_time_minutes': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': 'Global default',
            }),
        }
        help_texts = {
            'slug': 'Leave blank to auto-generate from the course name.',
            'icon': 'Optional emoji, e.g. 📘 📖 🕌 ⚖️',
            'order': 'Lower numbers appear first in dropdowns.',
            'default_question_count': 'Leave blank to use the global default from Site Settings.',
            'default_time_minutes': 'Leave blank to use the global default from Site Settings.',
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Course name is required.")
        return name

    def clean_default_question_count(self):
        value = self.cleaned_data.get('default_question_count')
        if value is not None and value < 1:
            raise forms.ValidationError("Question count must be at least 1.")
        return value

    def clean_default_time_minutes(self):
        value = self.cleaned_data.get('default_time_minutes')
        if value is not None and value < 1:
            raise forms.ValidationError("Time must be at least 1 minute.")
        return value


class QuestionBankForm(forms.ModelForm):
    """Form for creating/editing a CBT question."""

    class Meta:
        model = QuestionBank
        fields = [
            'course', 'topic', 'difficulty',
            'question_text',
            'option_a', 'option_b', 'option_c', 'option_d',
            'correct_option', 'explanation',
            'is_active',
        ]
        widgets = {
            'course': forms.Select(attrs={
                'class': 'form-control',
                'required': True,
            }),
            'topic': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Wudu, Salah, Tajweed',
            }),
            'difficulty': forms.Select(attrs={
                'class': 'form-control',
            }),
            'question_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Type the question here.',
                'required': True,
            }),
            'option_a': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Option A text',
                'required': True,
            }),
            'option_b': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Option B text',
                'required': True,
            }),
            'option_c': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Option C text',
                'required': True,
            }),
            'option_d': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Option D text',
                'required': True,
            }),
            'correct_option': forms.Select(attrs={
                'class': 'form-control',
                'required': True,
            }),
            'explanation': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional. Shown on the result page when answers are reviewed.',
            }),
        }
        labels = {
            'option_a': 'Option A',
            'option_b': 'Option B',
            'option_c': 'Option C',
            'option_d': 'Option D',
            'correct_option': 'Correct Answer',
        }
        help_texts = {
            'topic': 'Optional — used for filtering and per-topic breakdown.',
            'explanation': 'Optional but recommended. Helps students learn from mistakes.',
        }

    def clean(self):
        cleaned = super().clean()

        question_text = (cleaned.get('question_text') or '').strip()
        opt_a = (cleaned.get('option_a') or '').strip()
        opt_b = (cleaned.get('option_b') or '').strip()
        opt_c = (cleaned.get('option_c') or '').strip()
        opt_d = (cleaned.get('option_d') or '').strip()
        correct = (cleaned.get('correct_option') or '').strip().lower()

        if not question_text:
            self.add_error('question_text', "Question text is required.")
        if not opt_a:
            self.add_error('option_a', "Option A is required.")
        if not opt_b:
            self.add_error('option_b', "Option B is required.")
        if not opt_c:
            self.add_error('option_c', "Option C is required.")
        if not opt_d:
            self.add_error('option_d', "Option D is required.")
        if correct not in ('a', 'b', 'c', 'd'):
            self.add_error('correct_option', "Please select a valid correct answer.")

        # Detect duplicate options
        seen = {}
        for label, val in [('A', opt_a), ('B', opt_b), ('C', opt_c), ('D', opt_d)]:
            if val and val.lower() in seen:
                self.add_error(None,
                    f"Options {seen[val.lower()]} and {label} are identical. "
                    f"All four options must be unique."
                )
                break
            if val:
                seen[val.lower()] = label

        return cleaned        
        
        
        
        
        