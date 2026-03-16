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