# events/forms.py

from django import forms
from django.utils.text import slugify
from django.utils import timezone
from django.forms import inlineformset_factory
from .models import Event, EventLink


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'title', 'slug', 'description', 'category',
            'start_datetime', 'end_datetime', 'location',
            'image', 'is_featured', 'is_active', 'send_email',
            'hero_layout',  # <-- ADDED
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter event title...'
            }),
            'slug': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'auto-generated from title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Write your event description here...'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'start_datetime': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'end_datetime': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Engineering Mosque, ECE Lecture Hall'
            }),
            'is_featured': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'send_email': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'hero_layout': forms.Select(attrs={  # <-- ADDED
                'class': 'form-control'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].required = True
        self.fields['start_datetime'].required = True
        self.fields['end_datetime'].required = True
        self.fields['location'].required = True

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        if not slug:
            title = self.cleaned_data.get('title')
            if title:
                slug = slugify(title)
                original_slug = slug
                counter = 1
                while Event.objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
                    slug = f"{original_slug}-{counter}"
                    counter += 1
        return slug

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_datetime')
        end = cleaned_data.get('end_datetime')

        if start and end and end <= start:
            raise forms.ValidationError("End time must be after start time.")

        # Conflict checker
        location = cleaned_data.get('location')
        if start and end and location:
            conflicting = Event.objects.filter(
                location=location,
                is_active=True,
                start_datetime__lt=end,
                end_datetime__gt=start
            ).exclude(pk=self.instance.pk)
            if conflicting.exists():
                raise forms.ValidationError(
                    f"This venue is already booked during this time for: "
                    f"{', '.join([e.title for e in conflicting[:3]])}"
                )

        return cleaned_data


EventLinkFormSet = inlineformset_factory(
    Event,
    EventLink,
    fields=['url', 'link_type', 'description', 'is_primary'],
    extra=1,
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