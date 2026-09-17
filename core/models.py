from django.db import models
from django.utils import timezone


# Create your models here.
class SiteSettings(models.Model):
    # ============ MEMBERSHIP / TUTOR APPLICATIONS ============
    tutor_applications_open = models.BooleanField(
        default=False,
        help_text="Allow tutor applications?"
    )
    membership_applications_open = models.BooleanField(
        default=False,
        help_text="Allow membership applications?"
    )

    # ============ ISLAMIYYA ============
    islamiyya_registration_open = models.BooleanField(default=False)
    islamiyya_whatsapp_link = models.URLField(
        blank=True,
        null=True,
        help_text="Default WhatsApp group link for Islamiyya after verification"
    )

    # ============ TUTOR EVALUATIONS ============
    tutor_evaluations_open = models.BooleanField(
        default=False,
        help_text="Allow students to submit tutor evaluations?"
    )

    # ============ INTRO TEXTS ============
    tutor_intro_text = models.TextField(
        blank=True,
        default="Do you aspire to help your brothers and sisters overcome "
                "academic challenges? Join us as a tutor!"
    )
    membership_intro_text = models.TextField(
        blank=True,
        default="Join NAMETS – work fisabillah, only God can repay. "
                "We need dedicated brothers and sisters."
    )
    evaluation_intro_text = models.TextField(
        blank=True,
        default="Help us improve by evaluating your tutor."
    )

    # ============================================================
    # CBT — Computer-Based Testing (all toggles + defaults)
    # ============================================================
    cbt_enabled = models.BooleanField(
        default=False,
        help_text="Master switch. When OFF, students see 'CBT is currently disabled'."
    )
    cbt_show_on_public_nav = models.BooleanField(
        default=True,
        help_text="Show the CBT link in the public Academics navigation."
    )
    cbt_allow_difficulty_choice = models.BooleanField(
        default=True,
        help_text="Let students pick difficulty (Easy / Medium / Hard / Mixed)."
    )
    cbt_allow_topic_filter = models.BooleanField(
        default=False,
        help_text="Let students restrict the test to a specific topic."
    )
    cbt_show_answers = models.BooleanField(
        default=True,
        help_text="Show correct answers + explanations on the result page."
    )
    cbt_allow_retake = models.BooleanField(
        default=True,
        help_text="Show a 'Retake Test' button on the result page."
    )
    cbt_ai_report_enabled = models.BooleanField(
        default=True,
        help_text="Generate a personalized AI report on the result page (Gemini)."
    )
    cbt_default_question_count = models.PositiveIntegerField(
        default=20,
        help_text="Default number of questions when a student starts a test."
    )
    cbt_default_time_minutes = models.PositiveIntegerField(
        default=20,
        help_text="Default test duration in minutes."
    )
    cbt_min_questions = models.PositiveIntegerField(
        default=5,
        help_text="Minimum number of questions a student can request."
    )
    cbt_max_questions = models.PositiveIntegerField(
        default=50,
        help_text="Maximum number of questions a student can request."
    )
    cbt_grace_seconds = models.PositiveIntegerField(
        default=30,
        help_text="Grace window for late submission (network lag). Not shown to students."
    )
    cbt_tab_switch_warning_threshold = models.PositiveIntegerField(
        default=3,
        help_text="Show the honesty reminder once, after this many tab switches."
    )
    cbt_pre_test_verse = models.TextField(
        default="وَٱللَّهُ يَعْلَمُ وَأَنتُمْ لَا تَعْلَمُونَ\n\n"
                "\"And Allah knows, while you do not know.\" — Al-Baqarah 2:216",
        help_text="Ayah or Hadith shown on the pre-test screen. Keep it short."
    )
    cbt_pre_test_message = models.TextField(
        default="This test is for your own benefit. Allah sees your effort — "
                "be honest with yourself. Answer sincerely, and may this benefit you.",
        help_text="Short honesty reminder shown before the test starts."
    )

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return "NAMETS Site Settings"


class DailyEmailCounter(models.Model):
    date = models.DateField(unique=True, default=timezone.now)
    brevo_count = models.IntegerField(default=0)
    gmail_count = models.IntegerField(default=0)

    @classmethod
    def get_today(cls):
        obj, _ = cls.objects.get_or_create(date=timezone.now().date())
        return obj


class EmailLog(models.Model):
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=200)
    category = models.CharField(max_length=50)
    provider = models.CharField(max_length=20)   # Brevo, Gmail, or failed
    status = models.CharField(max_length=20)     # sent, failed
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.subject} → {self.recipient_email}"

import os
from django.db import models
from django.utils import timezone


def _slug_for_path(value, fallback='slide'):
    base = (value or fallback)[:40]
    base = ''.join(c if c.isalnum() or c in '-_' else '_' for c in base).strip('_')
    return base or fallback


import os
import uuid
from django.db import models
from django.utils import timezone


# ---------- upload path helpers ----------
def hero_desktop_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or '.webp'
    return f"hero/desktop/{uuid.uuid4().hex}{ext}"


def hero_mobile_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or '.webp'
    return f"hero/mobile/{uuid.uuid4().hex}{ext}"


class HeroSlide(models.Model):
    """
    Rotating hero banner on the public homepage.
    Each slide carries paired desktop + mobile images.
    Optionally up to two call-to-action buttons.

    Files stored under MEDIA_ROOT/hero/...
    """

    # ---------- text ----------
    title = models.CharField(
        max_length=200, blank=True,
        help_text="Main headline. Leave blank to hide."
    )
    subtitle = models.CharField(
        max_length=300, blank=True,
        help_text="Supporting line under the headline. Leave blank to hide."
    )

    # ---------- images ----------
    desktop_image = models.ImageField(
        upload_to=hero_desktop_path,
        help_text="Desktop image — 16:9, WebP recommended (1920 × 1080)",
    )
    mobile_image = models.ImageField(
        upload_to=hero_mobile_path,
        help_text="Mobile image — 4:5, WebP recommended (1080 × 1350)",
    )

    # ---------- primary button (optional) ----------
    primary_button_text = models.CharField(
        max_length=60, blank=True,
        help_text="e.g. 'Learn more'. Leave blank to hide the primary button."
    )
    primary_button_url = models.CharField(
        max_length=300, blank=True,
        help_text="e.g. /academics/ or https://…"
    )

    # ---------- secondary button (optional) ----------
    secondary_button_text = models.CharField(
        max_length=60, blank=True,
        help_text="e.g. 'View events'. Leave blank to hide the secondary button."
    )
    secondary_button_url = models.CharField(
        max_length=300, blank=True,
        help_text="e.g. /events/ or https://…"
    )

    # ---------- scheduling / ordering ----------
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    active_from  = models.DateTimeField(null=True, blank=True)
    active_until = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = 'Hero slide'
        verbose_name_plural = 'Hero slides'

    def __str__(self):
        return self.title or f"Hero slide #{self.pk}"

    # ---------- image URL helpers ----------
    @property
    def desktop_url(self):
        try:
            return self.desktop_image.url
        except Exception:
            return ''

    @property
    def mobile_url(self):
        try:
            return self.mobile_image.url
        except Exception:
            return ''

    # ---------- button helpers ----------
    @property
    def has_primary_button(self):
        return bool(self.primary_button_text and self.primary_button_url)

    @property
    def has_secondary_button(self):
        return bool(self.secondary_button_text and self.secondary_button_url)

    @property
    def has_any_button(self):
        return self.has_primary_button or self.has_secondary_button

    # ---------- text helpers ----------
    @property
    def has_custom_text(self):
        """True if this slide carries its own title or subtitle."""
        return bool((self.title or '').strip() or (self.subtitle or '').strip())

    # ---------- manager ----------
    @classmethod
    def active(cls):
        now = timezone.now()
        return (
            cls.objects
            .filter(is_active=True)
            .filter(models.Q(active_from__isnull=True) | models.Q(active_from__lte=now))
            .filter(models.Q(active_until__isnull=True) | models.Q(active_until__gte=now))
            .order_by('order', '-created_at')
        )