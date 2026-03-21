from django import forms
from .models import Question
from .models import TutorApplication, MembershipApplication, Skill

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
            'strong_courses': forms.Textarea(attrs={'rows':3}),
            'recommendations': forms.Textarea(attrs={'rows':3}),
            'past_experience': forms.Textarea(attrs={'rows':3}),
            'availability': forms.Textarea(attrs={'rows':3}),
        }

class MembershipApplicationForm(forms.ModelForm):
    skills = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select all that apply"
    )

    class Meta:
        model = MembershipApplication
        fields = '__all__'  # includes 'skills' and 'other_skill'
        widgets = {
            'how_work_with_people': forms.Textarea(attrs={'rows':3}),
            'recommendations': forms.Textarea(attrs={'rows':3}),
        }