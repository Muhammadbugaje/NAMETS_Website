from django import forms
from .models import TutorEvaluation


class ExcelUploadForm(forms.Form):
    excel_file = forms.FileField(label="Select Excel file", help_text="Columns: Student Name, Registration Number, Marks Obtained, Grade, Remarks (optional). First row should be headers.")
    

class TutorEvaluationForm(forms.ModelForm):
    class Meta:
        model = TutorEvaluation
        fields = ['tutor', 'student_name', 'rating', 'comments']
        widgets = {
            'rating': forms.RadioSelect(choices=TutorEvaluation.RATING_CHOICES),
            'comments': forms.Textarea(attrs={'rows': 4}),
        }
        labels = {
            'tutor': 'Select Tutor',
            'student_name': 'Your Name (optional)',
            'rating': 'Rating',
            'comments': 'Additional Comments (optional)',
        }

    def __init__(self, *args, **kwargs):
        course = kwargs.pop('course', None)
        super().__init__(*args, **kwargs)
        if course:
            self.fields['tutor'].queryset = course.tutors.filter(is_active=True)
            
            
class TimetableUploadForm(forms.Form):
    excel_file = forms.FileField(label="Select Excel file", help_text="Columns: Day (1-7), Time Start (HH:MM), Time End (HH:MM), Course Name, Venue, Entry Type (tutorial/islamiyya)")