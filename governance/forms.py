"""
Governance app — all forms.

Covers:
- TaskForm (with scope-aware assignee queryset)
- ProposalForm (with voting window + quorum validation)
- NominationIntakeForm
- SelectionRecordForm (with JSON snapshot editor)
"""

import json

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import Office, OfficeAssignment, Committee
from .models import Task, Proposal, NominationIntake, SelectionRecord

User = get_user_model()


# ============================================================
# HELPERS
# ============================================================

def _is_high_privilege(user):
    """
    Wakeel, ICT Head, or superuser — can assign tasks to anyone.
    Everyone else is scoped to their own office members.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if user.office_assignments.filter(
        is_active=True, office__is_protected=True
    ).exists():
        return True  # ICT Head
    return user.office_assignments.filter(
        is_active=True, office__name__icontains='wakeel'
    ).exists()  # Wakeel / Wakeelah


# ============================================================
# TASK FORM
# ============================================================

class TaskForm(forms.ModelForm):
    """
    Create/edit a task.

    Scope rules for `assigned_to`:
      - Wakeel / ICT / superuser → all active EXCO members
      - Anyone else             → only members of their own office(s)
                                  (plus themselves)

    The view MUST pass `user=request.user`.
    """

    class Meta:
        model = Task
        fields = [
            'title', 'description', 'priority', 'deadline',
            'assigned_to', 'assigned_office',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Prepare the semester report',
                'required': True,
                'autofocus': True,
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Add context, links, or anything the assignee needs…',
            }),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'deadline': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
            }),
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
            'assigned_office': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'assigned_to': 'Assign to a person',
            'assigned_office': 'Or assign to a whole office',
        }
        help_texts = {
            'assigned_to': 'Choose a specific person (leave blank to assign to an office instead).',
            'assigned_office': 'The task appears on every active member of that office’s dashboard.',
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # Deadline input accepts the datetime-local format
        self.fields['deadline'].input_formats = [
            '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M',
        ]

        # ---- Scope the assigned_to queryset ----
        if user:
            if _is_high_privilege(user):
                qs = User.objects.filter(
                    is_active=True,
                    office_assignments__is_active=True,
                ).distinct().order_by('first_name', 'last_name')
            else:
                office_ids = user.office_assignments.filter(
                    is_active=True
                ).values_list('office_id', flat=True)
                qs = User.objects.filter(
                    is_active=True,
                    office_assignments__is_active=True,
                    office_assignments__office_id__in=office_ids,
                ).distinct().order_by('first_name', 'last_name')

            # Always allow assigning to self
            if user.pk and not qs.filter(pk=user.pk).exists():
                qs = (qs | User.objects.filter(pk=user.pk)).distinct()

            self.fields['assigned_to'].queryset = qs

        # ---- assigned_office — all offices ----
        self.fields['assigned_office'].queryset = Office.objects.all().order_by('name')

        # ---- Not strictly required — clean() enforces exactly-one ----
        self.fields['assigned_to'].required = False
        self.fields['assigned_office'].required = False
        self.fields['deadline'].required = False

        # ---- Friendly empty labels ----
        self.fields['assigned_to'].empty_label = '— Select a person —'
        self.fields['assigned_office'].empty_label = '— Or select an office —'

    def clean(self):
        cleaned = super().clean()
        assigned_to = cleaned.get('assigned_to')
        assigned_office = cleaned.get('assigned_office')

        if not assigned_to and not assigned_office:
            raise ValidationError(
                "Assign the task to a person OR an office — at least one is required."
            )
        if assigned_to and assigned_office:
            raise ValidationError(
                "Assign the task to a person OR an office — not both."
            )

        return cleaned


# ============================================================
# PROPOSAL FORM
# ============================================================

class ProposalForm(forms.ModelForm):
    """
    Create/edit a proposal for a consensus vote.
    The view sets `proposed_by`, so it's not in the fields.
    """

    class Meta:
        model = Proposal
        fields = [
            'title', 'description', 'proposed_budget',
            'voting_start', 'voting_end',
            'quorum_percentage', 'approval_percentage',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "e.g. Purchase a new microphone for Da'awah events",
                'required': True,
                'autofocus': True,
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Explain the proposal — reasoning, benefits, alternatives considered, '
                               'and anything else voters should know…',
                'required': True,
            }),
            'proposed_budget': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '100',
                'min': '0',
                'placeholder': '0',
            }),
            'voting_start': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
            }),
            'voting_end': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
            }),
            'quorum_percentage': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '100',
            }),
            'approval_percentage': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '100',
            }),
        }
        help_texts = {
            'proposed_budget': 'Budget in Naira, if any. Leave 0 if not applicable.',
            'quorum_percentage': 'Minimum % of eligible voters who must vote for the result to count.',
            'approval_percentage': 'Minimum % of cast votes that must be "Agree" for the proposal to pass.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['voting_start'].input_formats = [
            '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M',
        ]
        self.fields['voting_end'].input_formats = [
            '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M',
        ]

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('voting_start')
        end = cleaned.get('voting_end')

        if start and end:
            if end <= start:
                self.add_error('voting_end', "Voting must end after it starts.")
            else:
                # Warn only if we're editing a draft — the view handles
                # whether new proposals can start in the past.
                duration = (end - start).total_seconds() / 3600
                if duration < 1:
                    self.add_error(
                        'voting_end',
                        "Voting window must be at least 1 hour long."
                    )

        quorum = cleaned.get('quorum_percentage')
        approval = cleaned.get('approval_percentage')

        if quorum is not None and not (1 <= quorum <= 100):
            self.add_error('quorum_percentage', "Must be between 1 and 100.")
        if approval is not None and not (1 <= approval <= 100):
            self.add_error('approval_percentage', "Must be between 1 and 100.")

        return cleaned


# ============================================================
# NOMINATION INTAKE FORM
# ============================================================

class NominationIntakeForm(forms.ModelForm):
    """
    Record a nomination for the incoming EXCO.
    The view sets `nominated_by`, so it's not in the fields.
    """

    class Meta:
        model = NominationIntake
        fields = [
            'nominated_name', 'nominated_email', 'nominated_phone',
            'nominated_office', 'session_label', 'reason', 'status',
        ]
        widgets = {
            'nominated_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Aminu Abdullahi Musa',
                'required': True,
                'autofocus': True,
            }),
            'nominated_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'aminu@example.com',
            }),
            'nominated_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '08012345678',
            }),
            'nominated_office': forms.Select(attrs={'class': 'form-control'}),
            'session_label': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 2025/2026',
            }),
            'reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Why is this person being nominated? '
                               'Mention their character, skills, and readiness.',
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'nominated_name': 'Nominee full name',
            'nominated_office': 'Office being nominated for',
            'session_label': 'Session',
        }
        help_texts = {
            'reason': 'Visible only to the Wakeel, ICT Head, and Shura Committee.',
            'status': 'Most nominations start as "Pending review".',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nominated_office'].queryset = Office.objects.all().order_by('name')
        self.fields['nominated_office'].empty_label = '— Select office —'
        self.fields['nominated_office'].required = False
        self.fields['nominated_email'].required = False
        self.fields['nominated_phone'].required = False
        self.fields['session_label'].required = False

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get('nominated_email')
        phone = cleaned.get('nominated_phone')
        if not email and not phone:
            raise ValidationError(
                "Provide at least one contact method (email or phone) for the nominee."
            )
        return cleaned


# ============================================================
# SELECTION RECORD FORM
# ============================================================

class SelectionRecordForm(forms.ModelForm):
    """
    Create/edit a SelectionRecord — the finalized list of who was selected.

    `snapshot` is a JSONField on the model. For ergonomics, this form
    exposes it as a JSON textarea with validation, so Shura members can
    paste or type the structured list directly.
    """

    snapshot_json = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 14,
            'style': 'font-family: monospace; font-size: 0.85rem; line-height: 1.5;',
            'placeholder': (
                '[\n'
                '  {"office": "Wakeel", "person_name": "Aminu Musa", "person_email": "aminu@example.com"},\n'
                '  {"office": "PRO I", "person_name": "Fatima Bello", "person_email": "fatima@example.com"}\n'
                ']'
            ),
        }),
        required=False,
        label='Selection snapshot (JSON)',
        help_text=(
            'A JSON array. Each entry should have: office, person_name, '
            'and (optional) person_email. Free-form fields are allowed.'
        ),
    )

    class Meta:
        model = SelectionRecord
        fields = ['session_label', 'notes', 'is_published']
        widgets = {
            'session_label': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 2025/2026',
                'required': True,
                'autofocus': True,
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Any notes about this selection — who was on the Shura, '
                               'dates, context, etc.',
            }),
        }
        labels = {
            'session_label': 'Session',
            'is_published': 'Publish to outgoing EXCO',
        }
        help_texts = {
            'is_published': 'When ON, this record is visible to the current EXCO.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['snapshot_json'].initial = json.dumps(
                self.instance.snapshot or [], indent=2, ensure_ascii=False
            )

    def clean_snapshot_json(self):
        raw = (self.cleaned_data.get('snapshot_json') or '').strip()
        if not raw:
            return []

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON — {e.msg} at line {e.lineno}, column {e.colno}.")

        if not isinstance(data, list):
            raise ValidationError(
                "The snapshot must be a JSON array — e.g. [ {...}, {...} ]."
            )

        for i, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValidationError(
                    f"Entry #{i + 1} must be an object (dictionary), not "
                    f"{type(item).__name__}."
                )
            if 'office' not in item and 'person_name' not in item:
                raise ValidationError(
                    f"Entry #{i + 1} must include at least 'office' or "
                    f"'person_name'. Got keys: {', '.join(item.keys()) or 'none'}."
                )

        return data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.snapshot = self.cleaned_data.get('snapshot_json', [])
        if commit:
            instance.save()
        return instance


from accounts.models import Committee


class OfficeForm(forms.ModelForm):
    class Meta:
        model = Office
        fields = ['name', 'committee', 'is_protected']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "e.g. PRO I, Da'awah Officer II, Librarian I",
                'required': True,
                'autofocus': True,
            }),
            'committee': forms.Select(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'committee': 'Which committee this office belongs to.',
            'is_protected': 'ICT Head only — this office is never touched by handover.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['committee'].required = False
        self.fields['committee'].empty_label = '— No committee —'




