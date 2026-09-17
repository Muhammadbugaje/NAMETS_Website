# communications/forms.py

from django import forms
from django.utils.text import slugify
from django.utils import timezone
from django.forms import inlineformset_factory

from .models import (
    Announcement, Link, PrayerSchedule, DonationCampaign,
    MosqueInfo, MosqueRule, MagazineIssue, Article, Subscriber
)


# ============================================================
# PUBLIC FORMS
# ============================================================

class SubscriptionForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'Your email address'})
    )
    notify_announcements = forms.BooleanField(
        required=False,
        label='New announcements'
    )
    notify_events = forms.BooleanField(
        required=False,
        label='Upcoming events'
    )
    notify_prayer_changes = forms.BooleanField(
        required=False,
        label='Prayer time changes'
    )


# ============================================================
# ADMIN FORMS
# ============================================================

class SubscriberForm(forms.ModelForm):
    class Meta:
        model = Subscriber
        fields = ['email', 'is_verified', 'is_active',
                  'notify_announcements', 'notify_events', 'notify_prayer_changes']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_verified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_announcements': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_events': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_prayer_changes': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = [
            'title', 'slug', 'content', 'image', 'category',
            'is_pinned', 'publish_at', 'expire_at',
            'is_active', 'send_email'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter announcement title...'
            }),
            'slug': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'auto-generated from title'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': 'Write your announcement content here...'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'publish_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'expire_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'is_pinned': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'send_email': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].required = True
        self.fields['publish_at'].required = True

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        if not slug:
            title = self.cleaned_data.get('title')
            if title:
                slug = slugify(title)
                original_slug = slug
                counter = 1
                while Announcement.objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
                    slug = f"{original_slug}-{counter}"
                    counter += 1
        return slug

    def clean(self):
        cleaned_data = super().clean()
        publish_at = cleaned_data.get('publish_at')
        expire_at = cleaned_data.get('expire_at')

        if publish_at and expire_at and expire_at < publish_at:
            raise forms.ValidationError("Expiry date cannot be before publish date.")

        return cleaned_data


# LinkFormSet — only ONE empty link form by default (instead of 3)
LinkFormSet = inlineformset_factory(
    Announcement,
    Link,
    fields=['url', 'link_type', 'description', 'is_primary'],
    extra=1,  # Changed from 3 to 1 for cleaner UI
    max_num=10,
    can_delete=True,
    widgets={
        'url': forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://...'
        }),
        'link_type': forms.Select(attrs={
            'class': 'form-control'
        }),
        'description': forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Optional description'
        }),
        'is_primary': forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
    }
)


class PrayerScheduleForm(forms.ModelForm):
    class Meta:
        model = PrayerSchedule
        fields = '__all__'  # includes all fields (date, adhan/iqama times, is_active, send_email)
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fajr_adhan': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'fajr_iqama': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'dhuhr_adhan': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'dhuhr_iqama': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'asr_adhan': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'asr_iqama': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'maghrib_adhan': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'maghrib_iqama': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'isha_adhan': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'isha_iqama': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'send_email': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned = super().clean()
        date = cleaned.get('date')
        if date and PrayerSchedule.objects.filter(date=date).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("A schedule for this date already exists.")
        return cleaned


class DonationCampaignForm(forms.ModelForm):
    class Meta:
        model = DonationCampaign
        fields = ['title', 'description', 'bank_details', 'goal_amount', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'bank_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'goal_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class MosqueInfoForm(forms.ModelForm):
    class Meta:
        model = MosqueInfo
        fields = ['location', 'description', 'imam_name', 'contact_email', 'contact_phone']
        widgets = {
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'imam_name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
        }


class MosqueRuleForm(forms.ModelForm):
    class Meta:
        model = MosqueRule
        fields = ['title', 'content', 'order', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class MagazineIssueForm(forms.ModelForm):
    class Meta:
        model = MagazineIssue
        fields = ['title', 'slug', 'description', 'cover_image', 'pdf_file', 'published_date', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'published_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        if not slug:
            slug = slugify(self.cleaned_data.get('title'))
        return slug


class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ['issue', 'title', 'slug', 'category', 'author', 'content', 'image', 'published_at', 'is_active']
        widgets = {
            'issue': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.TextInput(attrs={'class': 'form-control'}),
            'author': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 8}),
            'published_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        if not slug:
            slug = slugify(self.cleaned_data.get('title'))
        return slug