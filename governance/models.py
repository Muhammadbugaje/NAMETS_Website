"""
Governance app — oversight, accountability, and internal democratic process.

Covers:
- Audit log (sensitive actions, separate from the notification ActivityLog)
- Tasks (assignment, tracking, performance)
- Proposals & voting (consensus engine)
- Shura / Naqib workflow (nominations, selection records, oath acknowledgments)
- Handover (dissolve EXCO, graduation profiles)
- Delegation audit trail (office heads granting permissions to subordinates)
"""

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from accounts.models import Office, Department

User = get_user_model()


# ============================================================
# AUDIT LOG
# ============================================================

class AuditLog(models.Model):
    """
    Records *sensitive* actions only — permission changes, handover, vote
    cast, payment logged, delegation, bulk import/export.

    NOTE: This is deliberately separate from `namets_notifications.ActivityLog`,
    which records general content changes (a course edited, an announcement
    posted). AuditLog is for actions a reviewer would care about during an
    accountability review, and is only visible to office heads, the Wakeel,
    and the ICT Head.
    """

    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('permission_granted', 'Permission granted'),
        ('permission_revoked', 'Permission revoked'),
        ('vote_cast', 'Vote cast'),
        ('proposal_opened', 'Proposal opened for voting'),
        ('proposal_closed', 'Proposal closed'),
        ('handover', 'Handover / dissolve EXCO'),
        ('payment_logged', 'Payment logged'),
        ('bulk_import', 'Bulk import'),
        ('bulk_export', 'Bulk export'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audit_entries'
    )
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    office = models.ForeignKey(
        Office, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audit_entries',
        help_text="Office the actor was acting as, if known."
    )
    target_model = models.CharField(max_length=100, blank=True)
    target_id = models.IntegerField(null=True, blank=True)
    object_repr = models.CharField(max_length=300, blank=True)
    changes = models.JSONField(
        default=dict, blank=True,
        help_text="Free-form diff or details — e.g. {'before': ..., 'after': ...}"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'action']),
            models.Index(fields=['office', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
        ]
        verbose_name = 'Audit log entry'
        verbose_name_plural = 'Audit log'

    def __str__(self):
        who = self.user.get_full_name() if self.user else 'System'
        what = self.object_repr or self.get_action_display()
        return f"{who} · {what}"

    @property
    def actor_display(self):
        if not self.user:
            return 'System'
        return self.user.get_full_name() or self.user.username


    @property
    def changes_json_pretty(self):
        import json
        try:
            return json.dumps(self.changes or {}, indent=2, default=str, ensure_ascii=False)
        except Exception:
            return str(self.changes)



# ============================================================
# TASKS
# ============================================================

class Task(models.Model):
    """
    A single unit of work assigned to a person OR an entire office.

    Two assignment modes:
    - assigned_to a User       → personal task, shows on their dashboard
    - assigned_office an Office → office-wide task, shows on the office dashboard

    Exactly one of the two should be set. Validation enforces this.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Assignment
    assigned_to = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True,
        related_name='my_tasks',
        help_text="Assign to a specific person. Leave blank if assigning to a whole office."
    )
    assigned_office = models.ForeignKey(
        Office, on_delete=models.CASCADE, null=True, blank=True,
        related_name='tasks',
        help_text="Assign to an entire office. Leave blank if assigning to a person."
    )
    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tasks_created'
    )

    # Scheduling
    deadline = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default='medium'
    )

    # Progress
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    completion_proof = models.FileField(
        upload_to='task_proofs/', blank=True, null=True,
        help_text="Optional photo or document showing the task was done."
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tasks_completed'
    )

    # Optional link to any other object (event checklist item, proposal, etc.)
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['status', 'deadline', '-created_at']
        indexes = [
            models.Index(fields=['status', 'deadline']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['assigned_office', 'status']),
        ]
        verbose_name = 'Task'

    def __str__(self):
        return self.title

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.assigned_to and not self.assigned_office:
            raise ValidationError("Assign the task to a person OR an office.")
        if self.assigned_to and self.assigned_office:
            raise ValidationError("Assign the task to a person OR an office, not both.")

    # ---- Convenience ----

    @property
    def assignee_display(self):
        if self.assigned_to:
            return self.assigned_to.get_full_name() or self.assigned_to.username
        if self.assigned_office:
            return self.assigned_office.name
        return '—'

    @property
    def is_overdue(self):
        return (
            self.status in ('pending', 'in_progress')
            and self.deadline is not None
            and self.deadline < timezone.now()
        )

    @property
    def priority_color(self):
        return {
            'low': 'green',
            'medium': 'gold',
            'high': 'orange',
            'urgent': 'red',
        }.get(self.priority, 'gold')

    @property
    def status_color(self):
        if self.is_overdue:
            return 'red'
        return {
            'pending': 'gold',
            'in_progress': 'blue',
            'completed': 'green',
            'cancelled': 'grey',
        }.get(self.status, 'gold')

    def mark_completed(self, user, proof=None):
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.completed_by = user
        if proof:
            self.completion_proof = proof
        self.save(update_fields=[
            'status', 'completed_at', 'completed_by',
            'completion_proof', 'updated_at',
        ])

    @classmethod
    def for_user(cls, user, include_office=True):
        """Return tasks assigned to this user (direct + optionally office-wide)."""
        q = models.Q(assigned_to=user)
        if include_office:
            office_ids = user.office_assignments.filter(
                is_active=True
            ).values_list('office_id', flat=True)
            q |= models.Q(assigned_office_id__in=office_ids)
        return cls.objects.filter(q).distinct()


# ============================================================
# PROPOSALS & VOTING
# ============================================================

class Proposal(models.Model):
    """
    A proposal put to the EXCO for a consensus vote.

    Lifecycle:
        draft → voting → passed | rejected | cancelled

    The result is decided when voting_end passes, based on:
      - quorum: minimum % of eligible voters who must have voted
      - approval: minimum % of cast votes that must be 'agree'
    """

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('voting', 'Voting Open'),
        ('passed', 'Passed'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    proposed_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='proposals'
    )
    proposed_budget = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Budget in Naira, if any. Leave 0 if not applicable."
    )

    voting_start = models.DateTimeField()
    voting_end = models.DateTimeField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    quorum_percentage = models.PositiveIntegerField(
        default=60,
        help_text="Minimum % of eligible voters who must vote for the result to count."
    )
    approval_percentage = models.PositiveIntegerField(
        default=50,
        help_text="Minimum % of cast votes that must be 'Agree' for the proposal to pass."
    )

    # Outcome
    decided_at = models.DateTimeField(null=True, blank=True)
    result_summary = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['-voting_end']),
        ]

    def __str__(self):
        return self.title

    # ---- Election math ----

    @property
    def total_eligible_voters(self):
        """Every active EXCO member — i.e. anyone with at least one active office."""
        return User.objects.filter(
            office_assignments__is_active=True,
            is_active=True,
        ).distinct().count()

    @property
    def total_votes_cast(self):
        return self.votes.count()

    @property
    def agree_count(self):
        return self.votes.filter(choice='agree').count()

    @property
    def disagree_count(self):
        return self.votes.filter(choice='disagree').count()

    @property
    def abstain_count(self):
        return self.votes.filter(choice='abstain').count()

    @property
    def participation_percentage(self):
        eligible = self.total_eligible_voters
        if not eligible:
            return 0
        return round((self.total_votes_cast / eligible) * 100, 1)

    @property
    def quorum_reached(self):
        eligible = self.total_eligible_voters
        if not eligible:
            return False
        return self.participation_percentage >= self.quorum_percentage

    @property
    def approval_reached(self):
        cast = self.total_votes_cast
        if not cast:
            return False
        return (self.agree_count / cast) * 100 >= self.approval_percentage

    def user_can_vote(self, user):
        if self.status != 'voting':
            return False
        if not user.is_authenticated:
            return False
        if not user.office_assignments.filter(is_active=True).exists():
            return False
        return not self.votes.filter(voter=user).exists()

    def tally(self):
        """Snapshot of the current standing — used by admin dashboard + result page."""
        return {
            'eligible': self.total_eligible_voters,
            'cast': self.total_votes_cast,
            'agree': self.agree_count,
            'disagree': self.disagree_count,
            'abstain': self.abstain_count,
            'participation_pct': self.participation_percentage,
            'quorum_reached': self.quorum_reached,
            'approval_reached': self.approval_reached,
            'quorum_target': self.quorum_percentage,
            'approval_target': self.approval_percentage,
        }

    def decide(self, by_user=None, force=False):
        """
        Close the proposal and set its final status.
        Called manually, or by the scheduled job once voting_end has passed.
        `force` skips the voting_end check (used by admin override).
        """
        if self.status != 'voting':
            return self.status
        if not force and self.voting_end > timezone.now():
            return self.status  # window still open

        if not self.quorum_reached:
            self.status = 'rejected'
            self.result_summary = (
                f"Quorum not reached — only {self.participation_percentage}% "
                f"of eligible voters participated (needed {self.quorum_percentage}%)."
            )
        elif self.approval_reached:
            self.status = 'passed'
            self.result_summary = (
                f"Passed — {self.agree_count} agree / "
                f"{self.disagree_count} disagree / "
                f"{self.abstain_count} abstain "
                f"({self.participation_percentage}% participation)."
            )
        else:
            self.status = 'rejected'
            self.result_summary = (
                f"Rejected — only {round(self.agree_count / self.total_votes_cast * 100)}% "
                f"approved (needed {self.approval_percentage}%)."
            )

        self.decided_at = timezone.now()
        self.save(update_fields=['status', 'decided_at', 'result_summary', 'updated_at'])
        return self.status


class Vote(models.Model):
    """One EXCO member's vote on one proposal."""

    CHOICES = [
        ('agree', 'Agree'),
        ('disagree', 'Disagree'),
        ('abstain', 'Abstain'),
    ]

    proposal = models.ForeignKey(
        Proposal, on_delete=models.CASCADE, related_name='votes'
    )
    voter = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='votes_cast'
    )
    choice = models.CharField(max_length=20, choices=CHOICES)
    feedback = models.TextField(
        blank=True,
        help_text="Optional — why did you vote this way?"
    )
    cast_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('proposal', 'voter')
        ordering = ['-cast_at']

    def __str__(self):
        return f"{self.voter} → {self.proposal} ({self.choice})"


# ============================================================
# SHURA / NAQIB WORKFLOW
# ============================================================

class NominationIntake(models.Model):
    """
    A nomination for an incoming EXCO office — captured during the Shura
    Committee's selection window. Deliberation still happens offline; this
    just tracks the intake so nothing gets lost.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending review'),
        ('shortlisted', 'Shortlisted'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    nominated_name = models.CharField(max_length=200)
    nominated_email = models.EmailField(blank=True)
    nominated_phone = models.CharField(max_length=20, blank=True)
    nominated_office = models.ForeignKey(
        Office, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='nominations'
    )
    nominated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='nominations_made'
    )
    reason = models.TextField(
        blank=True,
        help_text="Why is this person being nominated?"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending'
    )
    session_label = models.CharField(
        max_length=50, blank=True,
        help_text="Session this is for, e.g. '2025/2026'."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.nominated_name} → {self.nominated_office}"


class SelectionRecord(models.Model):
    """
    One per session — the finalized list of who was selected for which office.
    The snapshot field preserves the outcome even if User/Office records change.
    """

    session_label = models.CharField(max_length=50, unique=True)
    finalized_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='selections_finalized'
    )
    finalized_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    is_published = models.BooleanField(
        default=False,
        help_text="When ON, the selection is visible to the outgoing EXCO."
    )
    # [{'office': '...', 'person_name': '...', 'person_email': '...'}, ...]
    snapshot = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['-finalized_at']

    def __str__(self):
        return self.session_label


class OathAcknowledgment(models.Model):
    """
    Timestamped record that a newly-selected EXCO member took the oath of
    allegiance on handover day (Bye-Law 7.3(e)).
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='oath_acknowledgments'
    )
    session_label = models.CharField(max_length=50)
    acknowledged_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ['-acknowledged_at']
        unique_together = ('user', 'session_label')

    def __str__(self):
        return f"{self.user} → {self.session_label}"


# ============================================================
# HANDOVER & GRADUATION
# ============================================================

class HandoverLog(models.Model):
    """Record of one handover run (dissolve EXCO)."""

    initiated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='handovers_initiated'
    )
    session_ending = models.CharField(max_length=50, blank=True)
    session_starting = models.CharField(max_length=50, blank=True)
    dissolved_count = models.PositiveIntegerField(default=0)
    protected_skipped = models.PositiveIntegerField(
        default=0,
        help_text="Active offices skipped because is_protected=True."
    )
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Handover on {self.timestamp:%Y-%m-%d %H:%M}"


    
class GraduationProfile(models.Model):
    """
    A digital yearbook entry for each NAMETS alumnus.

    Auto-filled at handover; the alumni can then edit their personal fields
    (final message, contact info, social links, photo).
    Visible to current EXCO + other alumni — never public.
    """

    # ---- Core link ----
    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='graduation_profile'
    )

    # ---- Auto-filled at handover (editable by admin if needed) ----
    graduation_year = models.PositiveIntegerField(
        db_index=True,
        help_text="Year they left the EXCO."
    )
    department_name = models.CharField(
        max_length=150, blank=True,
        help_text="Snapshot at graduation time."
    )
    phone_number = models.CharField(
        max_length=20, blank=True,
        help_text="Snapshot at graduation time — used for re-onboarding matches."
    )
    email = models.EmailField(
        blank=True,
        help_text="Snapshot at graduation time — used for re-onboarding matches."
    )
    offices_held = models.JSONField(
        default=list, blank=True,
        help_text="List of {office, display_label, is_active} dicts, snapshotted at handover."
    )
    tasks_completed = models.PositiveIntegerField(default=0)
    proposals_passed = models.PositiveIntegerField(default=0)

    # ---- Personal fields the alumni can edit themselves ----
    final_message = models.TextField(
        blank=True,
        help_text="A message to future NAMETS members. Shown on your profile."
    )
    current_occupation = models.CharField(
        max_length=200, blank=True,
        help_text="e.g. 'Software Engineer at XYZ', 'MSc Student at ABU'."
    )
    current_location = models.CharField(
        max_length=150, blank=True,
        help_text="e.g. 'Kaduna, Nigeria', 'Toronto, Canada'."
    )
    profile_photo = models.ImageField(
        upload_to='alumni_photos/', blank=True, null=True,
        help_text="Optional. If blank, initials are used."
    )
    social_links = models.JSONField(
        default=dict, blank=True,
        help_text="e.g. {'linkedin': 'url', 'twitter': '@handle', 'whatsapp': 'number'}"
    )

    # ---- Meta ----
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-graduation_year', 'user__first_name']
        indexes = [
            models.Index(fields=['graduation_year']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = 'Graduation profile'
        verbose_name_plural = 'Graduation profiles'

    def __str__(self):
        name = self.user.get_full_name() or self.user.username
        return f"{name} — Class of {self.graduation_year}"

    # ---------- Convenience ----------

    @property
    def display_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def initials(self):
        first = (self.user.first_name or '')[:1].upper()
        last = (self.user.last_name or '')[:1].upper()
        return f"{first}{last}" or '?'

    @property
    def primary_office(self):
        """Highest office held (first in the list)."""
        if self.offices_held:
            return self.offices_held[0].get('office', '')
        return ''

    @property
    def office_list_short(self):
        """Up to 3 offices, comma-separated, for compact display."""
        names = [o.get('office', '') for o in (self.offices_held or [])]
        names = [n for n in names if n]
        if not names:
            return '—'
        if len(names) <= 3:
            return ', '.join(names)
        return f"{', '.join(names[:3])} +{len(names) - 3} more"

    @property
    def is_editable_by(self):
        """Whether this profile is currently editable by the owner."""
        return True  # Always editable by owner

    @property
    def has_social_links(self):
        return bool(self.social_links) and any(self.social_links.values())
        
        
        
from django.db import models
from django.conf import settings
from django.utils import timezone


class SessionDocument(models.Model):
    """
    A session archive — magazine, report, constitution, minutes, photo album.

    Supported: PDF, PPTX, DOCX, images (uploaded) OR external link (Google Drive).
    Visibility: current EXCO + alumni + superusers.
    """

    # ---- Document types ----
    TYPE_MAGAZINE    = 'magazine'
    TYPE_REPORT      = 'report'
    TYPE_CONSTITUTION= 'constitution'
    TYPE_MINUTES     = 'minutes'
    TYPE_PHOTO_ALBUM = 'photo_album'
    TYPE_HANDOVER    = 'handover'
    TYPE_OTHER       = 'other'
    TYPE_CHOICES = [
        (TYPE_MAGAZINE,     'Session Magazine'),
        (TYPE_REPORT,       'Executive Report'),
        (TYPE_CONSTITUTION, 'Constitution / Bylaws'),
        (TYPE_MINUTES,      'Meeting Minutes'),
        (TYPE_PHOTO_ALBUM,  'Photo Album'),
        (TYPE_HANDOVER,     'Handover Document'),
        (TYPE_OTHER,        'Other'),
    ]

    # ---- Core fields ----
    title = models.CharField(max_length=250, db_index=True)
    description = models.TextField(
        blank=True,
        help_text="A short note about what this document contains.",
    )
    document_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_MAGAZINE,
        db_index=True,
    )

    # ---- Session ----
    session_label = models.CharField(
        max_length=20,
        help_text='e.g. "2023/2024" — shown as the session badge.',
    )
    session_year = models.PositiveIntegerField(
        db_index=True,
        help_text="The end year of the session (e.g. 2024 for 2023/2024). Used for sorting.",
    )

    # ---- Cover ----
    cover_image = models.ImageField(
        upload_to='session_docs/covers/',
        blank=True, null=True,
        help_text="Cover thumbnail (optional, but recommended for the archive grid).",
    )
    external_cover_url = models.URLField(
        max_length=500, blank=True,
        help_text="Or paste an external image URL (Google Drive, etc).",
    )

    # ---- File (upload OR external link) ----
    file = models.FileField(
        upload_to='session_docs/files/',
        blank=True, null=True,
        help_text="Upload the document. Supported: PDF, PPTX, DOCX, images.",
    )
    external_file_url = models.URLField(
        max_length=500, blank=True,
        help_text="Or link to the document (Google Drive, Dropbox, etc).",
    )
    external_file_label = models.CharField(
        max_length=80, blank=True, default='Open document',
    )

    # ---- Meta ----
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='session_documents_uploaded',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ---- Visibility flags ----
    is_published = models.BooleanField(
        default=True,
        help_text="Uncheck to hide from everyone except uploaders.",
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="Pin to the top of the archive for emphasis.",
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Lower numbers appear first within the same session.",
    )

    class Meta:
        ordering = ['-session_year', 'order', '-uploaded_at']
        verbose_name = 'Session document'
        verbose_name_plural = 'Session documents'
        indexes = [
            models.Index(fields=['-session_year']),
            models.Index(fields=['document_type']),
            models.Index(fields=['is_published']),
        ]

    def __str__(self):
        return f"{self.title} ({self.session_label})"

    # ---------- Convenience ----------

    @property
    def cover_url(self):
        """Prefer uploaded image, fall back to external URL."""
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
    def has_file(self):
        return bool(self.file) or bool(self.external_file_url)

    @property
    def file_url(self):
        """The download/view URL — external link wins, uploaded file falls back."""
        if self.external_file_url:
            return self.external_file_url
        try:
            if self.file:
                return self.file.url
        except Exception:
            pass
        return ''

    @property
    def file_label(self):
        if self.external_file_url:
            return self.external_file_label or 'Open document'
        return 'Download'

    @property
    def file_extension(self):
        """Best guess at file type for icon + preview decisions."""
        url = self.file_url.lower()
        for ext in ('pdf', 'pptx', 'ppt', 'docx', 'doc', 'xlsx', 'xls',
                    'png', 'jpg', 'jpeg', 'gif', 'webp'):
            if url.endswith('.' + ext):
                return ext
        return ''

    @property
    def file_icon(self):
        """Font Awesome icon class for the doc type."""
        ext = self.file_extension
        if ext == 'pdf':
            return 'fa-file-pdf'
        if ext in ('pptx', 'ppt'):
            return 'fa-file-powerpoint'
        if ext in ('docx', 'doc'):
            return 'fa-file-word'
        if ext in ('xlsx', 'xls'):
            return 'fa-file-excel'
        if ext in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
            return 'fa-file-image'
        return 'fa-file-alt'

    @property
    def is_pdf(self):
        return self.file_extension == 'pdf'

    @property
    def is_image(self):
        return self.file_extension in ('png', 'jpg', 'jpeg', 'gif', 'webp')

    @property
    def type_icon(self):
        """Icon for the document_type badge."""
        return {
            self.TYPE_MAGAZINE:     'fa-book-open',
            self.TYPE_REPORT:       'fa-clipboard-list',
            self.TYPE_CONSTITUTION: 'fa-scroll',
            self.TYPE_MINUTES:      'fa-file-signature',
            self.TYPE_PHOTO_ALBUM:  'fa-images',
            self.TYPE_HANDOVER:     'fa-handshake',
            self.TYPE_OTHER:        'fa-file',
        }.get(self.document_type, 'fa-file')        
        
        
        
        