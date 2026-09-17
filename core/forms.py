from django import forms
from .models import SiteSettings


class SiteSettingsForm(forms.ModelForm):
    """
    Single form covering all SiteSettings fields.
    Booleans stay as CheckboxInput and are styled as toggle switches in the template.
    """

    class Meta:
        model = SiteSettings
        fields = [
            # Applications
            'tutor_applications_open',
            'membership_applications_open',
            'tutor_intro_text',
            'membership_intro_text',
            # Islamiyya
            'islamiyya_registration_open',
            'islamiyya_whatsapp_link',
            # Tutor Evaluations
            'tutor_evaluations_open',
            'evaluation_intro_text',
            # CBT — master
            'cbt_enabled',
            'cbt_show_on_public_nav',
            # CBT — student experience
            'cbt_allow_difficulty_choice',
            'cbt_allow_topic_filter',
            'cbt_show_answers',
            'cbt_allow_retake',
            'cbt_ai_report_enabled',
            # CBT — defaults
            'cbt_default_question_count',
            'cbt_default_time_minutes',
            'cbt_min_questions',
            'cbt_max_questions',
            # CBT — integrity
            'cbt_grace_seconds',
            'cbt_tab_switch_warning_threshold',
            # CBT — pre-test
            'cbt_pre_test_verse',
            'cbt_pre_test_message',
        ]
        widgets = {
            'tutor_intro_text': forms.Textarea(attrs={
                'rows': 3, 'class': 'ss-input ss-textarea',
                'placeholder': 'Shown on the tutor application page…',
            }),
            'membership_intro_text': forms.Textarea(attrs={
                'rows': 3, 'class': 'ss-input ss-textarea',
                'placeholder': 'Shown on the membership application page…',
            }),
            'evaluation_intro_text': forms.Textarea(attrs={
                'rows': 3, 'class': 'ss-input ss-textarea',
                'placeholder': 'Shown above the tutor evaluation form…',
            }),
            'islamiyya_whatsapp_link': forms.URLInput(attrs={
                'class': 'ss-input',
                'placeholder': 'https://chat.whatsapp.com/…',
            }),
            'cbt_default_question_count': forms.NumberInput(attrs={
                'class': 'ss-input', 'min': 1, 'max': 200,
            }),
            'cbt_default_time_minutes': forms.NumberInput(attrs={
                'class': 'ss-input', 'min': 1, 'max': 300,
            }),
            'cbt_min_questions': forms.NumberInput(attrs={
                'class': 'ss-input', 'min': 1,
            }),
            'cbt_max_questions': forms.NumberInput(attrs={
                'class': 'ss-input', 'min': 1,
            }),
            'cbt_grace_seconds': forms.NumberInput(attrs={
                'class': 'ss-input', 'min': 0, 'max': 300,
            }),
            'cbt_tab_switch_warning_threshold': forms.NumberInput(attrs={
                'class': 'ss-input', 'min': 0, 'max': 20,
            }),
            'cbt_pre_test_verse': forms.Textarea(attrs={
                'rows': 3, 'class': 'ss-input ss-textarea',
                'placeholder': 'Ayah or Hadith shown before the test…',
            }),
            'cbt_pre_test_message': forms.Textarea(attrs={
                'rows': 3, 'class': 'ss-input ss-textarea',
                'placeholder': 'Short honesty reminder…',
            }),
        }

    # ---------- Validation ----------

    def clean(self):
        cleaned = super().clean()

        min_q = cleaned.get('cbt_min_questions')
        max_q = cleaned.get('cbt_max_questions')
        default_q = cleaned.get('cbt_default_question_count')

        if min_q and max_q and min_q > max_q:
            self.add_error('cbt_min_questions',
                "Minimum questions cannot exceed the maximum.")

        if default_q and min_q and default_q < min_q:
            self.add_error('cbt_default_question_count',
                f"Default must be at least {min_q} (the minimum).")

        if default_q and max_q and default_q > max_q:
            self.add_error('cbt_default_question_count',
                f"Default cannot exceed {max_q} (the maximum).")

        return cleaned
        
        
        
from django import forms
from .models import HeroSlide


class HeroSlideForm(forms.ModelForm):
    class Meta:
        model = HeroSlide
        fields = [
            'title', 'subtitle',
            'desktop_image', 'mobile_image',
            'primary_button_text', 'primary_button_url',
            'secondary_button_text', 'secondary_button_url',
            'is_active', 'order',
            'active_from', 'active_until',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g. Welcome to NAMETS',
            }),
            'subtitle': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 2,
                'placeholder': 'A short supporting line…',
            }),
            'primary_button_text': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': "e.g. Learn more",
            }),
            'primary_button_url': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': '/academics/  or  https://…',
            }),
            'secondary_button_text': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': "e.g. View events",
            }),
            'secondary_button_url': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': '/events/  or  https://…',
            }),
            'order': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'active_from': forms.DateTimeInput(
                attrs={'class': 'form-input', 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'active_until': forms.DateTimeInput(
                attrs={'class': 'form-input', 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['active_from'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['active_until'].input_formats = ['%Y-%m-%dT%H:%M']

    def clean(self):
        cleaned = super().clean()

        # Primary button — both or neither
        p_text = (cleaned.get('primary_button_text') or '').strip()
        p_url  = (cleaned.get('primary_button_url') or '').strip()
        if bool(p_text) ^ bool(p_url):
            raise forms.ValidationError(
                'Primary button: fill in both the text and the URL, or leave both blank.'
            )

        # Secondary button — both or neither
        s_text = (cleaned.get('secondary_button_text') or '').strip()
        s_url  = (cleaned.get('secondary_button_url') or '').strip()
        if bool(s_text) ^ bool(s_url):
            raise forms.ValidationError(
                'Secondary button: fill in both the text and the URL, or leave both blank.'
            )

        return cleaned        
        
        
        
        
        
        