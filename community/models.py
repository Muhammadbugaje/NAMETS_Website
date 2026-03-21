from django.db import models
from django.contrib.auth import get_user_model
from cloudinary.models import CloudinaryField
from core.models import SiteSettings  # for toggling

# Create your models here.

User = get_user_model()

class Patron(models.Model):
    name = models.CharField(max_length=200)
    designation = models.CharField(max_length=200, help_text="e.g., HOD Mechanical Engineering")
    bio = models.TextField(blank=True)
    image = CloudinaryField('image', folder='patrons', blank=True, null=True)
    hierarchy_order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first")
    is_active = models.BooleanField(default=True)
    email = models.EmailField(blank=True, help_text="For notifications")
    receive_notifications = models.BooleanField(default=False)

    class Meta:
        ordering = ['hierarchy_order', 'name']

    def __str__(self):
        return self.name


class ExecutiveYear(models.Model):
    year_label = models.CharField(max_length=50, help_text="e.g., 2024/2025")
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0, help_text="Most recent years should have lower numbers")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return self.year_label


class Executive(models.Model):
    name = models.CharField(max_length=200)
    role = models.CharField(max_length=200)
    photo = CloudinaryField('image', folder='executives', blank=True, null=True)
    contribution_summary = models.TextField(blank=True)
    year = models.ForeignKey(ExecutiveYear, on_delete=models.CASCADE, related_name='executives')
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return f"{self.name} – {self.role} ({self.year.year_label})"


class Developer(models.Model):
    name = models.CharField(max_length=200)
    role = models.CharField(max_length=200, help_text="e.g., Backend Developer")
    bio = models.TextField(blank=True)
    photo = CloudinaryField('image', folder='developers', blank=True, null=True)
    github_link = models.URLField(blank=True)
    linkedin_link = models.URLField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return self.name


class Question(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    question_text = models.TextField()
    category = models.CharField(max_length=100, blank=True)
    is_public = models.BooleanField(default=True, help_text="Approved for public display")
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"Q: {self.question_text[:50]}..."


class Answer(models.Model):
    question = models.OneToOneField(Question, on_delete=models.CASCADE, related_name='answer')
    answer_text = models.TextField()
    responded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    responded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Answer to: {self.question.question_text[:50]}..."


class AboutPage(models.Model):
    mission_statement = models.TextField()
    vision_statement = models.TextField()
    history = models.TextField(blank=True)
    established_year = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name = "About Page"
        verbose_name_plural = "About Page"

    def __str__(self):
        return "About NAMETS"
    

class Skill(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class TutorApplication(models.Model):
    # Basic info
    name = models.CharField(max_length=200)
    reg_number = models.CharField(max_length=50)
    department = models.CharField(max_length=200)
    cgpa = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    campus_residence = models.BooleanField(default=True, help_text="Live on campus?")

    # Preferences
    strong_courses = models.TextField(help_text="List courses you excel in")
    preferred_course = models.CharField(max_length=200, help_text="Course you'd like to tutor")
    comfort_level = models.IntegerField(choices=[(i,i) for i in range(1,6)], help_text="How comfortable are you teaching? (1-5)")

    # Qualifications
    teaching_skill_rating = models.IntegerField(choices=[(i,i) for i in range(1,6)], blank=True, null=True)
    recommendations = models.TextField(help_text="Names of lecturers, class reps, or others who can recommend you")
    past_experience = models.TextField(blank=True, help_text="Any previous tutoring experience")
    availability = models.TextField(help_text="When are you available?")

    # Materials
    has_materials = models.BooleanField(default=False, help_text="Do you have your own materials?")
    collaborate_on_materials = models.BooleanField(default=False, help_text="Open to collaborating to create standard materials?")

    # Metadata
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_processed = models.BooleanField(default=False, help_text="Admin has reviewed this application")

    def __str__(self):
        return f"{self.name} – {self.reg_number}"

class MembershipApplication(models.Model):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female'), ('O', 'Other')]
    ISLAMIC_LEVEL_CHOICES = [('beginner','Beginner'), ('intermediate','Intermediate'), ('advanced','Advanced')]
    QURAN_MEMORIZATION_CHOICES = [('none','None'), ('some','Some Surahs'), ('half','Half'), ('whole','Whole Quran')]
    STRONG_SUIT_CHOICES = [
        ('public_speaking','Public Speaking'),
        ('tech','Tech (Programming, Design)'),
        ('graphic_design','Graphic Design'),
        ('programming','Programming'),
        ('islamiya_tutor','Islamiya Tutor'),
        ('compassion','Compassion/Helping Others'),
        ('other','Other'),
    ]

    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    reg_number = models.CharField(max_length=50, blank=True, help_text="For students")
    department = models.CharField(max_length=200, blank=True)
    campus_residence = models.BooleanField(default=True)

    # Islamic background
    islamic_knowledge = models.CharField(max_length=20, choices=ISLAMIC_LEVEL_CHOICES)
    quran_memorization = models.CharField(max_length=10, choices=QURAN_MEMORIZATION_CHOICES)
    skills = models.ManyToManyField(Skill, blank=True, help_text="Select all that apply")
    other_skill = models.CharField(max_length=200, blank=True, help_text="If other, specify")

    # Personal qualities
    how_work_with_people = models.TextField(help_text="How do you work with people?")
    recommendations = models.TextField(help_text="Names of those who can recommend you")

    # Metadata
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_processed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} – {self.email}"
 
    
class ContactPhone(models.Model):
    label = models.CharField(max_length=100, help_text="e.g., President, Secretary, General Inquiry")
    phone_number = models.CharField(max_length=20)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.label}: {self.phone_number}"