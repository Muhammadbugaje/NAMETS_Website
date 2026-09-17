from django import forms
from django.utils.text import slugify
from .models import (
    Question, TutorApplication, MembershipApplication, Skill,
    Patron, ExecutiveYear, Executive, Developer, AboutPage,
    ContactPhone, SocialMediaLink, NAMETSDocument, Answer
)


class AskQuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['name', 'email', 'question_text', 'category']
        widgets = {
            'question_text': forms.Textarea(attrs={'rows': 4}),
        }
        labels = {
            'name': 'Your Name',
            'email': 'Email (optional)',
            'question_text': 'Your Question',
            'category': 'Category (optional)',
        }


class TutorApplicationForm(forms.ModelForm):
    class Meta:
        model = TutorApplication
        fields = '__all__'
        widgets = {
            'strong_courses': forms.Textarea(attrs={'rows': 3}),
            'recommendations': forms.Textarea(attrs={'rows': 3}),
            'past_experience': forms.Textarea(attrs={'rows': 3}),
            'availability': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if TutorApplication.objects.filter(email=email).exists():
            raise forms.ValidationError(
                "An application with this email already exists. Please check your status or use a different email."
            )
        return email


class MembershipApplicationForm(forms.ModelForm):
    skills = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select all that apply"
    )

    class Meta:
        model = MembershipApplication
        fields = '__all__'
        widgets = {
            'how_work_with_people': forms.Textarea(attrs={'rows': 3}),
            'recommendations': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if MembershipApplication.objects.filter(email=email).exists():
            raise forms.ValidationError(
                "An application with this email already exists. Please check your status or use a different email."
            )
        return email


# ============================================================
# ADMIN FORMS
# ============================================================

class PatronForm(forms.ModelForm):
    class Meta:
        model = Patron
        fields = ['name', 'slug', 'designation', 'bio', 'image', 'hierarchy_order', 'is_active', 'email', 'receive_notifications']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'hierarchy_order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'receive_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        if not slug:
            slug = slugify(self.cleaned_data.get('name'))
        return slug


class ExecutiveYearForm(forms.ModelForm):
    class Meta:
        model = ExecutiveYear
        fields = ['year_label', 'description', 'display_order', 'is_active']
        widgets = {
            'year_label': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ExecutiveForm(forms.ModelForm):
    class Meta:
        model = Executive
        fields = ['name', 'role', 'photo', 'contribution_summary', 'year', 'display_order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.TextInput(attrs={'class': 'form-control'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            'contribution_summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'year': forms.Select(attrs={'class': 'form-control'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class DeveloperForm(forms.ModelForm):
    class Meta:
        model = Developer
        fields = ['name', 'role', 'bio', 'photo', 'github_link', 'linkedin_link', 'display_order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.TextInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            'github_link': forms.URLInput(attrs={'class': 'form-control'}),
            'linkedin_link': forms.URLInput(attrs={'class': 'form-control'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class AboutPageForm(forms.ModelForm):
    class Meta:
        model = AboutPage
        fields = ['mission_statement', 'vision_statement', 'history', 'established_year']
        widgets = {
            'mission_statement': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'vision_statement': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'history': forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
            'established_year': forms.TextInput(attrs={'class': 'form-control'}),
        }


class QuestionAnswerForm(forms.ModelForm):
    class Meta:
        model = Answer
        fields = ['answer_text']
        widgets = {
            'answer_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
        }


class SkillForm(forms.ModelForm):
    class Meta:
        model = Skill
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ContactPhoneForm(forms.ModelForm):
    class Meta:
        model = ContactPhone
        fields = ['label', 'phone_number', 'order', 'is_active']
        widgets = {
            'label': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SocialMediaLinkForm(forms.ModelForm):
    class Meta:
        model = SocialMediaLink
        fields = ['platform', 'url', 'order', 'is_active']
        widgets = {
            'platform': forms.Select(attrs={'class': 'form-control'}),
            'url': forms.URLInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class NAMETSDocumentForm(forms.ModelForm):
    class Meta:
        model = NAMETSDocument
        fields = ['title', 'description', 'file', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }    
    
    
    