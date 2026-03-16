from django.db import models
from django.contrib.auth import get_user_model
from cloudinary.models import CloudinaryField

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