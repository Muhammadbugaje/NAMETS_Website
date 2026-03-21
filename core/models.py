from django.db import models

# Create your models here.
class SiteSettings(models.Model):
    tutor_applications_open = models.BooleanField(default=False, help_text="Allow tutor applications?")
    membership_applications_open = models.BooleanField(default=False, help_text="Allow membership applications?")
    tutor_evaluations_open = models.BooleanField(
        default=False,
        help_text="Allow students to submit tutor evaluations?"
    )
    # maybe add intro texts as editable fields
    tutor_intro_text = models.TextField(blank=True, default="Do you aspire to help your brothers and sisters overcome academic challenges? Join us as a tutor!")
    membership_intro_text = models.TextField(blank=True, default="Join NAMETS – work fisabillah, only God can repay. We need dedicated brothers and sisters.")
    evaluation_intro_text = models.TextField(
        blank=True,
        default="Help us improve by evaluating your tutor."
    )
    
    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return "NAMETS Site Settings"