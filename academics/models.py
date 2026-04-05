from django.db import models
from django.utils import timezone
from cloudinary.models import CloudinaryField

# Create your models here.

class Tutor(models.Model):
    name = models.CharField(max_length=200)
    bio = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

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
    # Option 1: Upload file directly
    file = CloudinaryField('file', folder='materials', blank=True, null=True)
    # Option 2: Google Drive link
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
    
def get_featured_materials(self):
    return self.materials.filter(is_active=True, is_featured=True)

def get_featured_evaluations(self):
    return self.evaluations.filter(is_active=True, is_featured=True)


class TimetableEntry(models.Model):
    DAYS_OF_WEEK = [
        (1, 'Monday'),
        (2, 'Tuesday'),
        (3, 'Wednesday'),
        (4, 'Thursday'),
        (5, 'Friday'),
        (6, 'Saturday'),
        (7, 'Sunday'),
    ]
    TYPE_CHOICES = [
        ('tutorial', 'Tutorial'),
        ('islamiyya', 'Islamiyya'),
    ]

    day = models.IntegerField(choices=DAYS_OF_WEEK)
    time_start = models.TimeField()
    time_end = models.TimeField()
    course_name = models.CharField(max_length=200)
    venue = models.CharField(max_length=200, blank=True)
    entry_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['entry_type', 'day', 'time_start', 'order']

    def __str__(self):
        return f"{self.get_entry_type_display()}: {self.course_name} - {self.get_day_display()} {self.time_start}"
    
    

class IslamiyyaCourse(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class IslamiyyaRegistration(models.Model):
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]

    # Personal details
    name = models.CharField(max_length=200)
    registration_number = models.CharField(max_length=50, help_text="Student ID or identification")
    gender = models.CharField(max_length=1, choices=[('M','Male'),('F','Female')], blank=True, null=True)
    photo = CloudinaryField('photo', folder='islamiyya_photos', blank=True, null=True)
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
    is_verified = models.BooleanField(default=False, help_text="Payment verified")
    verified_at = models.DateTimeField(blank=True, null=True)
    whatsapp_link = models.URLField(blank=True, null=True, help_text="WhatsApp group link (shown after verification)")

    # Admin control
    is_active = models.BooleanField(default=True, help_text="User's enrollment active (if false, they are deleted or expired)")

    class Meta:
        ordering = ['-submitted_at']

    def save(self, *args, **kwargs):
        if not self.application_id:
            # Generate unique ID: ISL-YYYY-XXXX (year and sequential)
            last = IslamiyyaRegistration.objects.order_by('-id').first()
            if last and last.application_id.startswith(f'ISL-{timezone.now().year}'):
                try:
                    num = int(last.application_id.split('-')[-1]) + 1
                except:
                    num = 1
            else:
                num = 1
            self.application_id = f"ISL-{timezone.now().year}-{num:04d}"
        if self.is_verified and not self.verified_at:
            self.verified_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.application_id})"
    

class UserResourceSubmission(models.Model):
    """Materials submitted by users, pending admin approval"""
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    file = CloudinaryField('file', folder='user_resources')
    submitted_by = models.CharField(max_length=100, blank=True)  # optional name
    email = models.EmailField(blank=True) 
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.title} ({self.status})"
     
class CompetitionResult(models.Model):
    event_name = models.CharField(max_length=200, help_text="e.g., NAMETS Week 2024")
    category = models.CharField(max_length=100, blank=True, help_text="e.g., Musabaqah 60 Hizb, Quiz Competition")
    position = models.CharField(max_length=50,blank=True, help_text="e.g 1st, 2nd, 3rd", default='participant')
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