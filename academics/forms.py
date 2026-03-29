from django import forms
from .models import TutorEvaluation
from .models import IslamiyyaRegistration, IslamiyyaCourse

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
    
    

class IslamiyyaRegistrationForm(forms.ModelForm):
    class Meta:
        model = IslamiyyaRegistration
        fields = ['name', 'email', 'gender', 'photo', 'phone', 'department', 'registration_number', 'level', 'courses', 'other_course']
        widgets = {
            'photo': forms.FileInput(),
            'courses': forms.CheckboxSelectMultiple(),
            'other_course': forms.TextInput(attrs={'placeholder': 'If other, specify course'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        courses = cleaned_data.get('courses')
        other = cleaned_data.get('other_course')
        if not courses and not other:
            self.add_error('courses', 'Please select at least one course or specify an other course.')
        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if IslamiyyaRegistration.objects.filter(email=email).exists():
            raise forms.ValidationError("An application with this email already exists. Please use a different email or check your status.")
        return email
       
class CheckStatusForm(forms.Form):
    identifier = forms.CharField(label="Email or Registration Number", max_length=200)