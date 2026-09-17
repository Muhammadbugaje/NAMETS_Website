# academics/models.py — complete, with Islamiyya payment system + attendance

from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.contrib.auth import get_user_model
from cloudinary.models import CloudinaryField
import os

User = get_user_model()


# ============================================================
# TUTORS (expanded — was just name/bio/is_active before)
# ============================================================

class Tutor(models.Model):
    """Tutor — both tutorial and Islamiyya. Linked to Course via M2M."""
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    bio = models.TextField(blank=True)
    photo = CloudinaryField(
        'photo', folder='namets/academics/tutors',
        resource_type='image', blank=True, null=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def teaches_islamiyya(self):
        return self.courses.filter(course_type='islamiyya').exists()

    @property
    def teaches_tutorial(self):
        return self.courses.filter(course_type='tutorial').exists()


# ============================================================
# COURSES (unchanged)
# ============================================================

class Course(models.Model):
    TYPE_CHOICES = [
        ('tutorial', 'Tutorial'),
        ('islamiyya', 'Islamiyya'),
    ]
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    course_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='tutorial')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    tutors = models.ManyToManyField(Tutor, blank=True, related_name='courses')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class TutorEvaluation(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='tutor_evaluations')
    tutor = models.ForeignKey(Tutor, on_delete=models.CASCADE, related_name='evaluations')
    student_name = models.CharField(max_length=200, blank=True, help_text="Optional – leave blank for anonymous")
    rating = models.IntegerField(choices=RATING_CHOICES)
    comments = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"Evaluation for {self.tutor.name} in {self.course.name} - Rating: {self.rating}"


class Session(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='sessions')
    title = models.CharField(max_length=200, blank=True)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    location = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['date', 'start_time']

    def __str__(self):
        return f"{self.course.name} - {self.date}"


class Material(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='materials')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = CloudinaryField('file', folder='namets/academics/materials', resource_type='auto', blank=True, null=True)
    drive_link = models.URLField(blank=True, null=True, help_text="Google Drive share link")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text="Show on course list page")

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.title


class Evaluation(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='evaluations')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateField()
    total_marks = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text="Show on course list page")

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.course.name} - {self.title}"


class Result(models.Model):
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='results')
    student_name = models.CharField(max_length=200)
    registration_number = models.CharField(max_length=50, blank=True, help_text="e.g., matric number")
    student_email = models.EmailField(blank=True, null=True)
    marks_obtained = models.DecimalField(max_digits=5, decimal_places=2)
    grade = models.CharField(max_length=2, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['student_name']

    def __str__(self):
        return f"{self.student_name} - {self.evaluation.title}"


class TimetableEntry(models.Model):
    DAYS_OF_WEEK = [
        (1, 'Monday'), (2, 'Tuesday'), (3, 'Wednesday'), (4, 'Thursday'),
        (5, 'Friday'), (6, 'Saturday'), (7, 'Sunday'),
    ]
    TYPE_CHOICES = [('tutorial', 'Tutorial'), ('islamiyya', 'Islamiyya')]
    LEVEL_CHOICES = [('level1', 'Level 1'), ('level2', 'Level 2')]

    day = models.IntegerField(choices=DAYS_OF_WEEK)
    time_start = models.TimeField()
    time_end = models.TimeField()
    course_name = models.CharField(max_length=200)
    venue = models.CharField(max_length=200, blank=True)
    entry_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='level1',
                             help_text="Which level this entry belongs to")

    class Meta:
        ordering = ['entry_type', 'level', 'day', 'time_start', 'order']

    def __str__(self):
        return f"{self.get_entry_type_display()}: {self.course_name} - {self.get_day_display()} {self.time_start}"


class IslamiyyaCourse(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# ============================================================
# ISLAMIYYA SETTINGS (NEW) — one row per academic session
# ============================================================

class IslamiyyaSettings(models.Model):
    """
    Configuration for one Islamiyya registration session.
    Example: one row for 2025/2026, one for 2026/2027.
    Only ONE row can be `is_active=True` at a time — that's the current session.
    """
    academic_session = models.CharField(
        max_length=20, help_text="e.g., 2025/2026"
    )
    is_open = models.BooleanField(
        default=False, help_text="Toggle to open/close registration for this session."
    )
    registration_opens_at = models.DateTimeField(
        null=True, blank=True, help_text="Optional — registration auto-opens at this time."
    )
    registration_closes_at = models.DateTimeField(
        null=True, blank=True, help_text="Optional — registration auto-closes at this time."
    )
    registration_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Fixed fee every student must pay for this session."
    )
    account = models.ForeignKey(
        'business.BankAccount', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='islamiyya_sessions',
        help_text="Bank account that receives Islamiyya payments for this session."
    )
    whatsapp_group_link = models.URLField(
        blank=True, null=True, help_text="Shown after payment is verified."
    )
    instructions = models.TextField(
        blank=True, help_text="Shown on the registration & payment pages."
    )
    is_active = models.BooleanField(
        default=True, help_text="Only ONE session can be active. Setting this replaces the previous active one."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-academic_session']
        verbose_name = "Islamiyya Setting"
        verbose_name_plural = "Islamiyya Settings"

    def __str__(self):
        return f"{self.academic_session} — ₦{self.registration_fee:,.2f}"

    def save(self, *args, **kwargs):
        if self.is_active:
            IslamiyyaSettings.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    @property
    def is_currently_open(self):
        if not self.is_open:
            return False
        now = timezone.now()
        if self.registration_opens_at and now < self.registration_opens_at:
            return False
        if self.registration_closes_at and now > self.registration_closes_at:
            return False
        return True

    @property
    def paid_count(self):
        return self.registrations.filter(payment_status='paid').count()

    @property
    def pending_count(self):
        return self.registrations.filter(payment_status='pending').count()

    @property
    def total_collected(self):
        from django.db.models import Sum
        return self.registrations.filter(
            payment_status='paid'
        ).aggregate(t=Sum('amount_paid'))['t'] or 0


# ============================================================
# ISLAMIYYA REGISTRATION (expanded with payment tracking)
# ============================================================

class IslamiyyaRegistration(models.Model):
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded'),
        ('waived', 'Fee Waived'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('paystack', 'Paystack (Online)'),
        ('manual', 'Manual (Mosque / Bank Transfer)'),
        ('cash', 'Cash at Mosque'),
        ('waived', 'Fee Waived by EXCO'),
    ]

    # Session
    session_settings = models.ForeignKey(
        IslamiyyaSettings, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='registrations',
        help_text="Which session this student is registering for."
    )

    # Personal details
    name = models.CharField(max_length=200)
    registration_number = models.CharField(max_length=50, help_text="Student ID or identification")
    gender = models.CharField(max_length=1, choices=[('M', 'Male'), ('F', 'Female')], blank=True, null=True)
    photo = CloudinaryField('photo', folder='namets/academics/islamiyya_photos',
                            resource_type='image', blank=True, null=True)
    department = models.CharField(max_length=200, blank=True, null=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)

    # Academic details
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner')
    courses = models.ManyToManyField(IslamiyyaCourse, blank=True, help_text="Select one or more courses")
    other_course = models.CharField(max_length=200, blank=True, help_text="If other, specify")

    # Application metadata
    application_id = models.CharField(max_length=100, unique=True, editable=False)
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, help_text="Enrollment active flag")

    # Payment tracking
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending'
    )
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True
    )
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_reference = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    # Manual verification (mosque payment)
    verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='islamiyya_verified'
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    # Refund (handled physically by EXCO)
    refunded_at = models.DateTimeField(null=True, blank=True)
    refunded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='islamiyya_refunded'
    )
    refund_note = models.TextField(blank=True)

    # WhatsApp link snapshot (from session at time of verification)
    whatsapp_link = models.URLField(blank=True, null=True)

    # Certificate (added on request)
    certificate_issued = models.BooleanField(default=False)
    certificate_issued_at = models.DateTimeField(null=True, blank=True)
    certificate_issued_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='islamiyya_certificates'
    )
    certificate_number = models.CharField(max_length=50, blank=True)

    # EXCO internal notes
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['payment_status']),
            models.Index(fields=['email']),
            models.Index(fields=['application_id']),
            models.Index(fields=['registration_number']),
        ]

    def __str__(self):
        return f"{self.name} ({self.application_id})"

    def save(self, *args, **kwargs):
        if not self.application_id:
            year = timezone.now().year
            last = IslamiyyaRegistration.objects.order_by('-id').first()
            if last and last.application_id.startswith(f'ISL-{year}'):
                try:
                    num = int(last.application_id.split('-')[-1]) + 1
                except Exception:
                    num = 1
            else:
                num = 1
            self.application_id = f"ISL-{year}-{num:04d}"
        super().save(*args, **kwargs)

    # --- Convenience properties ---

    @property
    def is_paid(self):
        return self.payment_status in ('paid', 'waived')

    @property
    def is_verified(self):
        """Legacy alias — kept for any code that still checks is_verified."""
        return self.is_paid

    @property
    def whatsapp_link_visible(self):
        return self.is_paid and self.whatsapp_link

    def mark_paid(self, amount, method, reference='', verified_by=None):
        """Called from Paystack callback or manual verification."""
        self.payment_status = 'paid'
        self.payment_method = method
        self.amount_paid = amount
        if reference:
            self.payment_reference = reference
        self.paid_at = timezone.now()
        if verified_by:
            self.verified_by = verified_by
            self.verified_at = timezone.now()
        # Snapshot the WhatsApp link from the session at time of payment
        if self.session_settings:
            self.whatsapp_link = self.session_settings.whatsapp_group_link or ''
        self.save()
        return True

    def mark_refunded(self, by_user, note=''):
        self.payment_status = 'refunded'
        self.refunded_at = timezone.now()
        self.refunded_by = by_user
        self.refund_note = note
        self.whatsapp_link = ''
        self.save()
        return True

    def mark_waived(self, by_user, note=''):
        self.payment_status = 'waived'
        self.payment_method = 'waived'
        self.verified_by = by_user
        self.verified_at = timezone.now()
        self.notes = (self.notes + '\n' + note).strip()
        if self.session_settings:
            self.whatsapp_link = self.session_settings.whatsapp_group_link or ''
        self.save()
        return True

    def issue_certificate(self, by_user):
        from django.db import transaction as db_transaction
        with db_transaction.atomic():
            year = timezone.now().year
            last = IslamiyyaRegistration.objects.filter(
                certificate_number__startswith=f'CERT-ISL-{year}-'
            ).order_by('-certificate_number').first()
            if last:
                try:
                    num = int(last.certificate_number.split('-')[-1]) + 1
                except Exception:
                    num = 1
            else:
                num = 1
            self.certificate_number = f'CERT-ISL-{year}-{num:04d}'
            self.certificate_issued = True
            self.certificate_issued_at = timezone.now()
            self.certificate_issued_by = by_user
            self.save()
        return self.certificate_number


# ============================================================
# RESOURCE SUBMISSIONS (unchanged)
# ============================================================

class UserResourceSubmission(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    file = CloudinaryField('file', folder='namets/academics/user_resources', resource_type='auto')
    submitted_by = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resources_reviewed'
    )
    review_note = models.TextField(blank=True)
    download_count = models.PositiveIntegerField(default=0)
    email_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.title} ({self.status})"


# ============================================================
# COMPETITION RESULTS (unchanged)
# ============================================================

class CompetitionResult(models.Model):
    event_name = models.CharField(max_length=200, help_text="e.g., NAMETS Week 2024")
    category = models.CharField(max_length=100, blank=True,
                                help_text="e.g., Musabaqah 60 Hizb, Quiz Competition")
    position = models.CharField(max_length=50, blank=True,
                                help_text="e.g 1st, 2nd, 3rd", default='participant')
    participant_name = models.CharField(max_length=200)
    department = models.CharField(max_length=200, blank=True)
    points = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    year = models.CharField(max_length=20, blank=True, help_text="e.g., 2025/2026")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first within category")

    class Meta:
        ordering = ['event_name', 'category', 'order', 'position']
        verbose_name_plural = "Competition Results"

    def __str__(self):
        return f"{self.event_name} - {self.position} - {self.participant_name}"


# ============================================================
# ATTENDANCE (NEW) — shared across tutorials, EXCO meetings, Islamiyya
# ============================================================

class AttendanceSession(models.Model):
    """A single attendance-taking event — one tutorial, one EXCO meeting,
    or one Islamiyya class session."""
    SESSION_TYPE = [
        ('tutorial', 'Tutorial'),
        ('exco_meeting', 'EXCO Meeting'),
        ('islamiyyah', 'Islamiyyah Class'),
        ('event', 'Event'),
    ]

    session_type = models.CharField(max_length=20, choices=SESSION_TYPE)
    course = models.ForeignKey(
        Course, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Set for tutorial sessions."
    )
    islamiyya_settings = models.ForeignKey(
        IslamiyyaSettings, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Set for Islamiyyah sessions."
    )
    title = models.CharField(max_length=200)
    date = models.DateField()
    taken_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='attendance_sessions_taken'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        verbose_name = "Attendance Session"
        verbose_name_plural = "Attendance Sessions"

    def __str__(self):
        return f"{self.get_session_type_display()}: {self.title} ({self.date})"

    @property
    def present_count(self):
        return self.records.filter(present=True).count()

    @property
    def total_count(self):
        return self.records.count()

class AttendanceRecord(models.Model):
    session = models.ForeignKey(
        AttendanceSession, on_delete=models.CASCADE, related_name='records'
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True,
        related_name='attendance_records'
    )
    islamiyya_registration = models.ForeignKey(
        IslamiyyaRegistration, on_delete=models.CASCADE, null=True, blank=True,
        related_name='attendance_records'
    )
    manual_name = models.CharField(
        max_length=200, blank=True,
        help_text="For manually-added attendees (not linked to a user or registration)"
    )
    manual_role = models.CharField(
        max_length=200, blank=True,
        help_text="e.g. Guest, Imam, External Supervisor"
    )
    present = models.BooleanField(default=False)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['session', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'user'],
                name='unique_attendance_per_user_per_session',
                condition=models.Q(user__isnull=False),
            ),
            models.UniqueConstraint(
                fields=['session', 'islamiyya_registration'],
                name='unique_attendance_per_registration_per_session',
                condition=models.Q(islamiyya_registration__isnull=False),
            ),
        ]

    @property
    def display_name(self):
        if self.user:
            return self.user.get_full_name() or self.user.username
        if self.islamiyya_registration:
            return self.islamiyya_registration.name
        return self.manual_name or '(unnamed)'

    @property
    def display_role(self):
        if self.user:
            active = self.user.office_assignments.filter(is_active=True).first()
            return active.display_label or active.office.name if active else ''
        if self.islamiyya_registration:
            return f"Islamiyya · {self.islamiyya_registration.get_level_display()}"
        return self.manual_role or ''
    
    
    
# ============================================================
# CBT MODULE — Courses, Questions
# ============================================================

from django.utils.text import slugify as _slugify


class CBTCourse(models.Model):
    """
    A course that can be used in CBT tests.
    Completely separate from the general Course model — CBT courses
    are their own pool, only what's registered here appears in CBT.
    """

    # ---- Core ----
    name = models.CharField(
        max_length=200,
        help_text="Shown to students on the CBT setup page."
    )
    slug = models.SlugField(
        max_length=220,
        unique=True,
        help_text="Auto-generated from name if left blank."
    )
    description = models.TextField(
        blank=True,
        help_text="Short description shown on the CBT home page."
    )
    instructions = models.TextField(
        blank=True,
        help_text="Optional. Shown above the test for this course only."
    )

    # ---- Display ----
    icon = models.CharField(
        max_length=10,
        blank=True,
        default='📘',
        help_text="Optional emoji shown next to the course name."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive courses are hidden from students."
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Lower numbers appear first."
    )

    # ---- Per-course overrides (blank = use global SiteSettings value) ----
    default_question_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Leave blank to use the global default."
    )
    default_time_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Leave blank to use the global default."
    )

    # ---- Meta ----
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_cbt_courses'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'CBT Course'
        verbose_name_plural = 'CBT Courses'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = _slugify(self.name)[:200] or 'course'
            slug = base
            counter = 2
            while CBTCourse.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    # ---- Convenience counts (used by admin + public) ----
    def question_count(self):
        return self.questions.filter(is_active=True).count()

    def easy_count(self):
        return self.questions.filter(is_active=True, difficulty='easy').count()

    def medium_count(self):
        return self.questions.filter(is_active=True, difficulty='medium').count()

    def hard_count(self):
        return self.questions.filter(is_active=True, difficulty='hard').count()

    def has_enough_questions(self, minimum=1):
        return self.question_count() >= minimum

    def get_default_question_count(self):
        """Return per-course override, else global default."""
        if self.default_question_count:
            return self.default_question_count
        try:
            from core.models import SiteSettings
            site = SiteSettings.objects.first()
            return site.cbt_default_question_count if site else 20
        except Exception:
            return 20

    def get_default_time_minutes(self):
        """Return per-course override, else global default."""
        if self.default_time_minutes:
            return self.default_time_minutes
        try:
            from core.models import SiteSettings
            site = SiteSettings.objects.first()
            return site.cbt_default_time_minutes if site else 20
        except Exception:
            return 20


class QuestionBank(models.Model):
    """
    A single multiple-choice question.
    Questions are written manually or imported from Excel — never AI.
    """

    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]

    OPTION_CHOICES = [
        ('a', 'A'),
        ('b', 'B'),
        ('c', 'C'),
        ('d', 'D'),
    ]

    SOURCE_CHOICES = [
        ('manual', 'Manual entry'),
        ('excel', 'Excel import'),
    ]

    # ---- Classification ----
    course = models.ForeignKey(
        CBTCourse,
        on_delete=models.CASCADE,
        related_name='questions',
    )
    topic = models.CharField(
        max_length=120,
        blank=True,
        help_text="Optional. e.g. 'Wudu', 'Salah', 'Tajweed'."
    )
    difficulty = models.CharField(
        max_length=10,
        choices=DIFFICULTY_CHOICES,
        default='medium',
    )

    # ---- Question body ----
    question_text = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500)
    correct_option = models.CharField(
        max_length=1,
        choices=OPTION_CHOICES,
        help_text="Which of the four options is correct."
    )
    explanation = models.TextField(
        blank=True,
        help_text="Optional. Shown on the result page when answers are reviewed."
    )

    # ---- Status ----
    source = models.CharField(
        max_length=10,
        choices=SOURCE_CHOICES,
        default='manual',
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive questions never appear in tests."
    )

    # ---- Meta ----
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_cbt_questions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ---- Anonymous aggregate stats (no student identity stored) ----
    times_answered = models.PositiveIntegerField(default=0)
    times_correct = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['course', 'difficulty', 'is_active']),
            models.Index(fields=['course', 'topic']),
        ]
        verbose_name = 'CBT Question'
        verbose_name_plural = 'CBT Questions'

    def __str__(self):
        prefix = f"[{self.course.name}]"
        text = self.question_text[:60]
        if len(self.question_text) > 60:
            text += '…'
        return f"{prefix} {text}"

    @property
    def correct_rate(self):
        """Return % correct or None if never answered."""
        if not self.times_answered:
            return None
        return round((self.times_correct / self.times_answered) * 100, 1)

    @property
    def difficulty_color(self):
        return {'easy': 'green', 'medium': 'gold', 'hard': 'red'}.get(self.difficulty, 'gold')    
    
    
from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils import timezone


class BookCategory(models.Model):
    """Categories like Islamic Studies, Engineering, Fiction, Reference…"""
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=50, blank=True,
        help_text="Font Awesome class, e.g. 'fa-book-quran'"
    )
    color = models.CharField(
        max_length=20, blank=True, default='#0F3D2E',
        help_text="Hex color for category accent, e.g. #C8A951"
    )
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Book category'
        verbose_name_plural = 'Book categories'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def book_count(self):
        return self.books.filter(inventory_item__is_active=True).count()


class Book(models.Model):
    """
    An e-library book — pure digital. No borrowing, no stock.
    Just browse, preview, and download.
    """

    # ---- Basic info ----
    title = models.CharField(max_length=250, db_index=True)
    description = models.TextField(blank=True)
    author = models.CharField(max_length=200, blank=True)
    isbn = models.CharField('ISBN', max_length=20, blank=True)
    publisher = models.CharField(max_length=200, blank=True)
    publication_year = models.PositiveIntegerField(null=True, blank=True)
    edition = models.CharField(max_length=50, blank=True)
    pages = models.PositiveIntegerField(null=True, blank=True)
    language = models.CharField(max_length=50, blank=True, default='English')

    # ---- Category ----
    category = models.ForeignKey(
        BookCategory,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='books',
    )

    # ---- Cover ----
    cover_image = models.ImageField(
        upload_to='library/covers/',
        blank=True, null=True,
        help_text="Upload a cover image, or paste an external URL below.",
    )
    external_cover_url = models.URLField(
        max_length=500, blank=True,
        help_text="Or paste a hosted image URL (Google Drive, etc).",
    )

    # ---- File (upload OR external link) ----
    file = models.FileField(
        upload_to='library/files/',
        blank=True, null=True,
        help_text="Upload the book (PDF, EPUB, etc).",
    )
    external_file_url = models.URLField(
        max_length=500, blank=True,
        help_text="Or link to the book (Google Drive, archive.org, etc).",
    )
    external_file_label = models.CharField(
        max_length=80, blank=True, default='Download',
    )

    # ---- Flags ----
    is_featured = models.BooleanField(
        default=False,
        help_text="Show in the 'Featured' strip on the library home.",
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Lower numbers appear first.",
    )
    is_published = models.BooleanField(
        default=True,
        help_text="Uncheck to hide this book from the public library.",
    )

    # ---- Meta ----
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='books_uploaded',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'title']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['is_featured']),
            models.Index(fields=['is_published']),
            models.Index(fields=['title']),
        ]
        verbose_name = 'Book'
        verbose_name_plural = 'Books'

    def __str__(self):
        return self.title

    # ---------- Convenience ----------

    @property
    def cover_url(self):
        try:
            if self.cover_image:
                return self.cover_image.url
        except Exception:
            pass
        return self.external_cover_url or ''

    @property
    def has_cover(self):
        return bool(self.cover_url)

    @property
    def download_url(self):
        """External link wins; uploaded file is fallback."""
        if self.external_file_url:
            return self.external_file_url
        try:
            if self.file:
                return self.file.url
        except Exception:
            pass
        return ''

    @property
    def has_file(self):
        return bool(self.download_url)

    @property
    def download_label(self):
        return self.external_file_label or 'Download'

    @property
    def file_extension(self):
        url = (self.download_url or '').lower()
        for ext in ('pdf', 'epub', 'mobi', 'docx', 'doc', 'pptx', 'ppt',
                    'txt', 'zip', 'png', 'jpg', 'jpeg'):
            if url.endswith('.' + ext):
                return ext
        return ''

    @property
    def file_icon(self):
        ext = self.file_extension
        if ext == 'pdf':
            return 'fa-file-pdf'
        if ext == 'epub':
            return 'fa-book-open'
        if ext == 'mobi':
            return 'fa-tablet-alt'
        if ext in ('docx', 'doc'):
            return 'fa-file-word'
        if ext in ('pptx', 'ppt'):
            return 'fa-file-powerpoint'
        if ext == 'zip':
            return 'fa-file-archive'
        if ext in ('png', 'jpg', 'jpeg'):
            return 'fa-file-image'
        return 'fa-file-download'

    @property
    def is_pdf(self):
        return self.file_extension == 'pdf'

    @property
    def is_image(self):
        return self.file_extension in ('png', 'jpg', 'jpeg')    
    
    
class CBTViolation(models.Model):
    """
    A single anti-cheating violation logged during a CBT attempt.

    Attempts are identified by an `attempt_id` — a string generated
    client-side and stored in sessionStorage for the duration of the
    test. When the tab is closed, the attempt ends.
    """

    TYPE_TAB_SWITCH    = 'tab_switch'
    TYPE_FULLSCREEN    = 'fullscreen_exit'
    TYPE_COPY          = 'copy_attempt'
    TYPE_PASTE         = 'paste_attempt'
    TYPE_RIGHT_CLICK   = 'right_click'
    TYPE_DEVTOOLS      = 'devtools'

    VIOLATION_TYPES = [
        (TYPE_TAB_SWITCH,  'Switched away from the test tab'),
        (TYPE_FULLSCREEN,  'Exited fullscreen mode'),
        (TYPE_COPY,        'Attempted to copy content'),
        (TYPE_PASTE,       'Attempted to paste content'),
        (TYPE_RIGHT_CLICK, 'Right-clicked inside the test'),
        (TYPE_DEVTOOLS,    'Dev tools opened / suspected'),
    ]

    attempt_id = models.CharField(
        max_length=64, db_index=True,
        help_text="Client-generated ID tying multiple violations to one attempt.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cbt_violations',
    )
    course = models.ForeignKey(
        'CBTCourse',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='violations',
    )
    violation_type = models.CharField(max_length=30, choices=VIOLATION_TYPES)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    metadata = models.JSONField(
        default=dict, blank=True,
        help_text="Extra context, e.g. question index, time elapsed.",
    )

    # Optional: flag if this violation triggered the auto-submit
    triggered_submit = models.BooleanField(default=False)

    class Meta:
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['attempt_id', 'occurred_at']),
            models.Index(fields=['-occurred_at']),
            models.Index(fields=['user', '-occurred_at']),
        ]
        verbose_name = 'CBT Violation'
        verbose_name_plural = 'CBT Violations'

    def __str__(self):
        return f"{self.get_violation_type_display()} — {self.user or 'anon'} ({self.occurred_at:%Y-%m-%d %H:%M})"

    @property
    def type_icon(self):
        return {
            self.TYPE_TAB_SWITCH:  'fa-window-restore',
            self.TYPE_FULLSCREEN:  'fa-compress',
            self.TYPE_COPY:        'fa-copy',
            self.TYPE_PASTE:       'fa-paste',
            self.TYPE_RIGHT_CLICK: 'fa-mouse-pointer',
            self.TYPE_DEVTOOLS:    'fa-code',
        }.get(self.violation_type, 'fa-exclamation-triangle')    
    
    
    
    
    