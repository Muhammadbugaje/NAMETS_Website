from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models


class User(AbstractUser):
    """Custom User model with email as the login identifier."""
    
    # Email is required and unique
    email = models.EmailField(unique=True)
    
    # Profile fields
    middle_name = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    matric_number = models.CharField(max_length=20, blank=True)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)
    address = models.TextField(blank=True)
    social_links = models.JSONField(default=dict, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    profile_completion_percentage = models.IntegerField(default=0)
    year_of_graduation = models.IntegerField(null=True, blank=True)  
    current_session = models.CharField(max_length=20, blank=True) 
    # Account lifecycle
    is_alumni = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=True)
    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
    )
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    # Protected Super Admin (ICT Head)
    is_super_protected = models.BooleanField(default=False)

    # Use email as the login identifier
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    def calculate_profile_completion(self):
        """Calculate profile completion percentage."""
        fields = [
            'first_name', 'last_name', 'email', 'phone_number',
            'matric_number', 'department', 'address', 'profile_picture'
        ]
        filled = sum(1 for f in fields if getattr(self, f))
        if self.social_links and any(self.social_links.values()):
            filled += 1
        total = len(fields) + 1
        self.profile_completion_percentage = min(int((filled / total) * 100), 100)
        self.save(update_fields=['profile_completion_percentage'])
        return self.profile_completion_percentage

    def delete(self, *args, **kwargs):
        if self.is_super_protected:
            raise PermissionError(
                "This account is protected and cannot be deleted through normal means. "
                "See the break-glass procedure in the governance app."
            )
        super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"

class Department(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)


class Committee(models.Model):
    name = models.CharField(max_length=100)
    def __str__(self):
        return self.name


class Office(models.Model):
    """Single Office definition — no duplicates."""
    name = models.CharField(max_length=100)
    is_protected = models.BooleanField(default=False)
    permissions = models.ManyToManyField(Permission, blank=True)
    linked_group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    duties = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, default='📋')
    is_custom_dashboard = models.BooleanField(default=False)
    dashboard_template = models.CharField(max_length=100, blank=True)

    # NEW FIELDS
    committee = models.ForeignKey(Committee, on_delete=models.SET_NULL, null=True, blank=True)
    head_of_committee = models.BooleanField(default=False)
    can_manage_all_offices = models.BooleanField(default=False)

    def can_manage(self, target_office):
        if self.is_protected:
            return True
        if target_office.is_protected:
            return False
        if self.can_manage_all_offices:
            return True
        if self.head_of_committee and self.committee_id == target_office.committee_id:
            return True
        return False

    def __str__(self):
        return self.name

    def get_dashboard_template(self):
        if self.is_custom_dashboard and self.dashboard_template:
            return self.dashboard_template
        return 'dashboards/offices/dynamic.html'

    def current_holders(self):
        from .models import OfficeAssignment
        return User.objects.filter(
            office_assignments__office=self,
            office_assignments__is_active=True
        )


class OfficeAssignment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='office_assignments')
    office = models.ForeignKey(Office, on_delete=models.CASCADE)
    display_label = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'office')

    def __str__(self):
        label = self.display_label or self.office.name
        return f"{self.user.get_full_name()} → {label}"