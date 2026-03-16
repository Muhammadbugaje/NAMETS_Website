from django import forms
from .models import Question

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