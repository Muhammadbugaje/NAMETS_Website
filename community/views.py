from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from . import selectors
from .forms import AskQuestionForm

from .models import TutorApplication, MembershipApplication
from core.models import SiteSettings
from .forms import TutorApplicationForm, MembershipApplicationForm
from core.services.webhooks import send_webhook

def patron_list(request):
    patrons = selectors.get_active_patrons()
    return render(request, 'community/patron_list.html', {'patrons': patrons})

def executive_list(request):
    years = selectors.get_executive_years()
    selected_year_id = request.GET.get('year')

    if selected_year_id and selected_year_id.isdigit():
        executives = selectors.get_executives_by_year(int(selected_year_id))
        selected_year = get_object_or_404(ExecutiveYear, id=selected_year_id)
    else:
        first_year = years.first()
        executives = selectors.get_executives_by_year(first_year.id if first_year else None)
        selected_year = first_year

    return render(request, 'community/executive_list.html', {
        'years': years,
        'executives': executives,
        'selected_year': selected_year,
    })

def question_list(request):
    questions = selectors.get_public_questions()
    return render(request, 'community/question_list.html', {'questions': questions})

def ask_question(request):
    if request.method == 'POST':
        form = AskQuestionForm(request.POST)
        if form.is_valid():
            question = form.save()
            messages.success(request, 'Your question has been submitted and will appear after moderation.')
            return redirect('community:question_list')
    else:
        form = AskQuestionForm()
    return render(request, 'community/ask_question.html', {'form': form})

def about_page(request):
    about = selectors.get_about_info()
    developers = selectors.get_active_developers()
    return render(request, 'community/about.html', {
        'about': about,
        'developers': developers,
    })
    
def developer_list(request):
    developers = selectors.get_active_developers()
    return render(request, 'community/developer_list.html', {'developers': developers})


def tutor_application(request):
    settings = SiteSettings.objects.first()
    if not settings or not settings.tutor_applications_open:
        return render(request, 'community/application_closed.html', {'type': 'tutor'})

    if request.method == 'POST':
        form = TutorApplicationForm(request.POST)
        if form.is_valid():
            application = form.save()
            # Send webhook to n8n for email notification
            send_webhook('tutor_application_submitted', {
                'recipients': [application.email],
                'name': application.name,
                'email': application.email,
                'phone': application.phone,
                'preferred_course': application.preferred_course,
            })
            messages.success(request, 'Your application has been submitted. We will contact you soon.')
            return redirect('core:homepage')
    else:
        form = TutorApplicationForm()

    return render(request, 'community/tutor_application.html', {'form': form, 'intro': settings.tutor_intro_text})

def membership_application(request):
    settings = SiteSettings.objects.first()
    if not settings or not settings.membership_applications_open:
        return render(request, 'community/application_closed.html', {'type': 'membership'})

    if request.method == 'POST':
        form = MembershipApplicationForm(request.POST)
        if form.is_valid():
            application = form.save()
            send_webhook('membership_application_submitted', {
                'recipients': [application.email],
                'name': application.name,
                'email': application.email,
                'phone': application.phone,
                'gender': application.gender,
                'skills': ', '.join([skill.name for skill in application.skills.all()])
            })
            messages.success(request, 'Your membership application has been submitted. We will contact you soon.')
            return redirect('core:homepage')
    else:
        form = MembershipApplicationForm()

    return render(request, 'community/membership_application.html', {'form': form, 'intro': settings.membership_intro_text})