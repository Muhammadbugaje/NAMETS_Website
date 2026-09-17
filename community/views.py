
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.text import slugify
from django.forms import inlineformset_factory
from django import forms

from core.email_utils import send_templated_email
from django.http import JsonResponse

from django.core.paginator import Paginator

from . import selectors
from .models import (
    Patron, ExecutiveYear, Executive, Developer, Question, Answer,
    AboutPage, Skill, TutorApplication, MembershipApplication,
    ContactPhone, SocialMediaLink, NAMETSDocument
)
from .forms import (
    AskQuestionForm, TutorApplicationForm, MembershipApplicationForm,
    PatronForm, ExecutiveYearForm, ExecutiveForm, DeveloperForm,
    AboutPageForm, SkillForm, ContactPhoneForm, SocialMediaLinkForm,
    NAMETSDocumentForm, QuestionAnswerForm
)
from core.models import SiteSettings
from core.email_utils import send_templated_email

import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# ============================================================
# PUBLIC VIEWS (Keep as they are)
# ============================================================

def patron_list(request):
    patrons = selectors.get_active_patrons()
    return render(request, 'community/patron_list.html', {'patrons': patrons})

def patron_detail(request, slug):
    patron = get_object_or_404(Patron, slug=slug, is_active=True)
    return render(request, 'community/patron_detail.html', {'patron': patron})


def executive_list(request):
    years = selectors.get_executive_years()
    selected_year_id = request.GET.get('year')
    show_all = (selected_year_id == 'all')

    if selected_year_id and selected_year_id.isdigit():
        selected_year = get_object_or_404(ExecutiveYear, id=selected_year_id)
        executives = selectors.get_executives_by_year(selected_year.id)
    elif show_all:
        selected_year = None
        executives = Executive.objects.filter(is_active=True).select_related('year')
    else:
        # Default: current (latest) year
        selected_year = years.first()
        executives = selectors.get_executives_by_year(
            selected_year.id if selected_year else None
        )

    # Only active, and always respect display_order
    executives = executives.filter(is_active=True).order_by('display_order', 'name')

    # Paginate — 12 per page
    paginator = Paginator(executives, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'community/executive_list.html', {
        'years': years,
        'selected_year': selected_year,
        'executives': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'is_paginated': page_obj.has_other_pages(),
        'total_count': paginator.count,
        'show_all': show_all,
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
    documents = NAMETSDocument.objects.filter(is_active=True).order_by('-uploaded_at')
    
    query = request.GET.get('q', '')
    if query:
        documents = documents.filter(Q(title__icontains=query) | Q(description__icontains=query))
    
    paginator = Paginator(documents, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'community/about.html', {
        'about': about,
        'developers': developers,
        'page_obj': page_obj,
        'query': query,
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
            send_templated_email(
                subject="NAMETS Tutor Application Received",
                recipients=[application.email],
                template_name='emails/application_received.html',
                context={
                    'name': application.name,
                    'type': 'Tutor',
                    'course': application.preferred_course,
                },
            )
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
            send_templated_email(
                subject="NAMETS Membership Application Received",
                recipients=[application.email],
                template_name='emails/application_received.html',
                context={
                    'name': application.name,
                    'type': 'Membership',
                    'course': None,
                },
            )
            messages.success(request, 'Your membership application has been submitted. We will contact you soon.')
            return redirect('core:homepage')
    else:
        form = MembershipApplicationForm()

    return render(request, 'community/membership_application.html', {'form': form, 'intro': settings.membership_intro_text})


# ============================================================
# ADMIN/EXCO VIEWS
# ============================================================

# ===== PATRONS ADMIN =====

@login_required
def admin_patron_list(request):
    if not request.user.has_perm('community.view_patron'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    # Bulk actions
    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if ids and action == 'delete' and request.user.has_perm('community.delete_patron'):
            count = Patron.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} patron(s) deleted.")
            return redirect('community:admin_patron_list')
        elif ids and action == 'activate' and request.user.has_perm('community.change_patron'):
            count = Patron.objects.filter(id__in=ids).update(is_active=True)
            messages.success(request, f"✅ {count} patron(s) activated.")
            return redirect('community:admin_patron_list')
        elif ids and action == 'deactivate' and request.user.has_perm('community.change_patron'):
            count = Patron.objects.filter(id__in=ids).update(is_active=False)
            messages.success(request, f"✅ {count} patron(s) deactivated.")
            return redirect('community:admin_patron_list')

    query = request.GET.get('q', '')
    patrons = Patron.objects.all().order_by('hierarchy_order', 'name')
    if query:
        patrons = patrons.filter(Q(name__icontains=query) | Q(designation__icontains=query))

    paginator = Paginator(patrons, 20)
    page = request.GET.get('page')
    patrons_page = paginator.get_page(page)

    return render(request, 'community/admin/patron_list.html', {
        'patrons': patrons_page,
        'page_obj': patrons_page,
        'is_paginated': patrons_page.has_other_pages(),
        'query': query,
    })


@login_required
def admin_patron_create(request):
    if not request.user.has_perm('community.add_patron'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_patron_list')

    if request.method == 'POST':
        form = PatronForm(request.POST, request.FILES)
        if form.is_valid():
            patron = form.save()
            messages.success(request, f"✅ Patron '{patron.name}' created.")
            return redirect('community:admin_patron_list')
    else:
        form = PatronForm()

    return render(request, 'community/admin/patron_form.html', {
        'form': form,
        'title': 'Add Patron',
        'button_text': 'Create Patron',
    })


@login_required
def admin_patron_edit(request, pk):
    patron = get_object_or_404(Patron, pk=pk)
    if not request.user.has_perm('community.change_patron'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_patron_list')

    if request.method == 'POST':
        form = PatronForm(request.POST, request.FILES, instance=patron)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Patron '{patron.name}' updated.")
            return redirect('community:admin_patron_list')
    else:
        form = PatronForm(instance=patron)

    return render(request, 'community/admin/patron_form.html', {
        'form': form,
        'patron': patron,
        'title': 'Edit Patron',
        'button_text': 'Update Patron',
    })


@login_required
def admin_patron_delete(request, pk):
    patron = get_object_or_404(Patron, pk=pk)
    if not request.user.has_perm('community.delete_patron'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_patron_list')

    if request.method == 'POST':
        name = patron.name
        patron.delete()
        messages.success(request, f"🗑️ Patron '{name}' deleted.")
        return redirect('community:admin_patron_list')

    return render(request, 'community/admin/patron_confirm_delete.html', {'patron': patron})


# ===== EXECUTIVE YEARS ADMIN =====

@login_required
def admin_executive_year_list(request):
    if not request.user.has_perm('community.view_executiveyear'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if ids and action == 'delete' and request.user.has_perm('community.delete_executiveyear'):
            count = ExecutiveYear.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} year(s) deleted.")
            return redirect('community:admin_executive_year_list')

    years = ExecutiveYear.objects.all().order_by('display_order')
    return render(request, 'community/admin/executive_year_list.html', {'years': years})


@login_required
def admin_executive_year_create(request):
    if not request.user.has_perm('community.add_executiveyear'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_executive_year_list')

    if request.method == 'POST':
        form = ExecutiveYearForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Executive year created.")
            return redirect('community:admin_executive_year_list')
    else:
        form = ExecutiveYearForm()

    return render(request, 'community/admin/executive_year_form.html', {
        'form': form,
        'title': 'Add Executive Year',
        'button_text': 'Create Year',
    })


@login_required
def admin_executive_year_edit(request, pk):
    year = get_object_or_404(ExecutiveYear, pk=pk)
    if not request.user.has_perm('community.change_executiveyear'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_executive_year_list')

    if request.method == 'POST':
        form = ExecutiveYearForm(request.POST, instance=year)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Executive year updated.")
            return redirect('community:admin_executive_year_list')
    else:
        form = ExecutiveYearForm(instance=year)

    return render(request, 'community/admin/executive_year_form.html', {
        'form': form,
        'year': year,
        'title': 'Edit Executive Year',
        'button_text': 'Update Year',
    })


@login_required
def admin_executive_year_delete(request, pk):
    year = get_object_or_404(ExecutiveYear, pk=pk)
    if not request.user.has_perm('community.delete_executiveyear'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_executive_year_list')

    if request.method == 'POST':
        label = year.year_label
        year.delete()
        messages.success(request, f"🗑️ Year '{label}' deleted.")
        return redirect('community:admin_executive_year_list')

    return render(request, 'community/admin/executive_year_confirm_delete.html', {'year': year})


# ===== EXECUTIVES ADMIN =====

@login_required
def admin_executive_list(request):
    if not request.user.has_perm('community.view_executive'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if ids and action == 'delete' and request.user.has_perm('community.delete_executive'):
            count = Executive.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} executive(s) deleted.")
            return redirect('community:admin_executive_list')
        elif ids and action == 'activate' and request.user.has_perm('community.change_executive'):
            count = Executive.objects.filter(id__in=ids).update(is_active=True)
            messages.success(request, f"✅ {count} executive(s) activated.")
            return redirect('community:admin_executive_list')
        elif ids and action == 'deactivate' and request.user.has_perm('community.change_executive'):
            count = Executive.objects.filter(id__in=ids).update(is_active=False)
            messages.success(request, f"✅ {count} executive(s) deactivated.")
            return redirect('community:admin_executive_list')

    query = request.GET.get('q', '')
    year_filter = request.GET.get('year', '')
    executives = Executive.objects.all().order_by('display_order', 'name')

    if query:
        executives = executives.filter(Q(name__icontains=query) | Q(role__icontains=query))
    if year_filter:
        executives = executives.filter(year_id=year_filter)

    paginator = Paginator(executives, 20)
    page = request.GET.get('page')
    executives_page = paginator.get_page(page)

    years = ExecutiveYear.objects.filter(is_active=True)

    return render(request, 'community/admin/executive_list.html', {
        'executives': executives_page,
        'page_obj': executives_page,
        'is_paginated': executives_page.has_other_pages(),
        'query': query,
        'year_filter': year_filter,
        'years': years,
    })


@login_required
def admin_executive_create(request):
    if not request.user.has_perm('community.add_executive'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_executive_list')

    if request.method == 'POST':
        form = ExecutiveForm(request.POST, request.FILES)
        if form.is_valid():
            executive = form.save()
            messages.success(request, f"✅ Executive '{executive.name}' created.")
            return redirect('community:admin_executive_list')
    else:
        form = ExecutiveForm()

    return render(request, 'community/admin/executive_form.html', {
        'form': form,
        'title': 'Add Executive',
        'button_text': 'Create Executive',
    })


@login_required
def admin_executive_edit(request, pk):
    executive = get_object_or_404(Executive, pk=pk)
    if not request.user.has_perm('community.change_executive'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_executive_list')

    if request.method == 'POST':
        form = ExecutiveForm(request.POST, request.FILES, instance=executive)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Executive '{executive.name}' updated.")
            return redirect('community:admin_executive_list')
    else:
        form = ExecutiveForm(instance=executive)

    return render(request, 'community/admin/executive_form.html', {
        'form': form,
        'executive': executive,
        'title': 'Edit Executive',
        'button_text': 'Update Executive',
    })


@login_required
def admin_executive_delete(request, pk):
    executive = get_object_or_404(Executive, pk=pk)
    if not request.user.has_perm('community.delete_executive'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_executive_list')

    if request.method == 'POST':
        name = executive.name
        executive.delete()
        messages.success(request, f"🗑️ Executive '{name}' deleted.")
        return redirect('community:admin_executive_list')

    return render(request, 'community/admin/executive_confirm_delete.html', {'executive': executive})


# ===== DEVELOPERS ADMIN =====

@login_required
def admin_developer_list(request):
    if not request.user.has_perm('community.view_developer'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if ids and action == 'delete' and request.user.has_perm('community.delete_developer'):
            count = Developer.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} developer(s) deleted.")
            return redirect('community:admin_developer_list')
        elif ids and action == 'activate' and request.user.has_perm('community.change_developer'):
            count = Developer.objects.filter(id__in=ids).update(is_active=True)
            messages.success(request, f"✅ {count} developer(s) activated.")
            return redirect('community:admin_developer_list')
        elif ids and action == 'deactivate' and request.user.has_perm('community.change_developer'):
            count = Developer.objects.filter(id__in=ids).update(is_active=False)
            messages.success(request, f"✅ {count} developer(s) deactivated.")
            return redirect('community:admin_developer_list')

    query = request.GET.get('q', '')
    developers = Developer.objects.all().order_by('display_order', 'name')
    if query:
        developers = developers.filter(Q(name__icontains=query) | Q(role__icontains=query))

    paginator = Paginator(developers, 20)
    page = request.GET.get('page')
    developers_page = paginator.get_page(page)

    return render(request, 'community/admin/developer_list.html', {
        'developers': developers_page,
        'page_obj': developers_page,
        'is_paginated': developers_page.has_other_pages(),
        'query': query,
    })


@login_required
def admin_developer_create(request):
    if not request.user.has_perm('community.add_developer'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_developer_list')

    if request.method == 'POST':
        form = DeveloperForm(request.POST, request.FILES)
        if form.is_valid():
            developer = form.save()
            messages.success(request, f"✅ Developer '{developer.name}' created.")
            return redirect('community:admin_developer_list')
    else:
        form = DeveloperForm()

    return render(request, 'community/admin/developer_form.html', {
        'form': form,
        'title': 'Add Developer',
        'button_text': 'Create Developer',
    })


@login_required
def admin_developer_edit(request, pk):
    developer = get_object_or_404(Developer, pk=pk)
    if not request.user.has_perm('community.change_developer'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_developer_list')

    if request.method == 'POST':
        form = DeveloperForm(request.POST, request.FILES, instance=developer)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Developer '{developer.name}' updated.")
            return redirect('community:admin_developer_list')
    else:
        form = DeveloperForm(instance=developer)

    return render(request, 'community/admin/developer_form.html', {
        'form': form,
        'developer': developer,
        'title': 'Edit Developer',
        'button_text': 'Update Developer',
    })


@login_required
def admin_developer_delete(request, pk):
    developer = get_object_or_404(Developer, pk=pk)
    if not request.user.has_perm('community.delete_developer'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_developer_list')

    if request.method == 'POST':
        name = developer.name
        developer.delete()
        messages.success(request, f"🗑️ Developer '{name}' deleted.")
        return redirect('community:admin_developer_list')

    return render(request, 'community/admin/developer_confirm_delete.html', {'developer': developer})


# ===== ABOUT PAGE ADMIN (Singleton) =====

@login_required
def admin_about_edit(request):
    if not request.user.has_perm('community.change_aboutpage'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    about = AboutPage.objects.first()
    if not about:
        about = AboutPage.objects.create(
            mission_statement="Our mission is to serve the Muslim engineering community.",
            vision_statement="To be the leading Muslim engineering student association."
        )

    if request.method == 'POST':
        form = AboutPageForm(request.POST, instance=about)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ About page updated.")
            return redirect('community:admin_about_edit')
    else:
        form = AboutPageForm(instance=about)

    return render(request, 'community/admin/about_edit.html', {
        'form': form,
        'about': about,
    })


# ===== QUESTIONS & ANSWERS ADMIN =====

@login_required
def admin_question_list(request):
    if not request.user.has_perm('community.view_question'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if ids and action == 'delete' and request.user.has_perm('community.delete_question'):
            count = Question.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} question(s) deleted.")
            return redirect('community:admin_question_list')
        elif ids and action == 'approve' and request.user.has_perm('community.change_question'):
            count = Question.objects.filter(id__in=ids).update(is_public=True)
            messages.success(request, f"✅ {count} question(s) approved for public display.")
            return redirect('community:admin_question_list')
        elif ids and action == 'unapprove' and request.user.has_perm('community.change_question'):
            count = Question.objects.filter(id__in=ids).update(is_public=False)
            messages.success(request, f"✅ {count} question(s) unapproved.")
            return redirect('community:admin_question_list')

    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')

    questions = Question.objects.all().order_by('-submitted_at')
    if query:
        questions = questions.filter(
            Q(name__icontains=query) |
            Q(question_text__icontains=query) |
            Q(category__icontains=query)
        )
    if status_filter == 'public':
        questions = questions.filter(is_public=True)
    elif status_filter == 'pending':
        questions = questions.filter(is_public=False)

    paginator = Paginator(questions, 20)
    page = request.GET.get('page')
    questions_page = paginator.get_page(page)

    return render(request, 'community/admin/question_list.html', {
        'questions': questions_page,
        'page_obj': questions_page,
        'is_paginated': questions_page.has_other_pages(),
        'query': query,
        'status_filter': status_filter,
    })


@login_required
def admin_question_answer(request, pk):
    question = get_object_or_404(Question, pk=pk)
    if not request.user.has_perm('community.change_question'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_question_list')

    # Check if answer exists
    try:
        answer = question.answer
    except Answer.DoesNotExist:
        answer = None

    if request.method == 'POST':
        form = QuestionAnswerForm(request.POST, instance=answer)
        if form.is_valid():
            answer_instance = form.save(commit=False)
            answer_instance.question = question
            answer_instance.responded_by = request.user
            answer_instance.save()
            # Also mark question as public if not already
            if not question.is_public:
                question.is_public = True
                question.save()
            messages.success(request, f"✅ Answer saved for '{question.question_text[:50]}...'")
            return redirect('community:admin_question_list')
    else:
        form = QuestionAnswerForm(instance=answer)

    return render(request, 'community/admin/question_answer.html', {
        'form': form,
        'question': question,
        'answer': answer,
    })


# ===== TUTOR APPLICATIONS ADMIN =====

@login_required
def admin_tutor_application_list(request):
    if not request.user.has_perm('community.view_tutorapplication'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if ids and action == 'delete' and request.user.has_perm('community.delete_tutorapplication'):
            count = TutorApplication.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} application(s) deleted.")
            return redirect('community:admin_tutor_application_list')
        elif ids and action == 'mark_processed' and request.user.has_perm('community.change_tutorapplication'):
            count = TutorApplication.objects.filter(id__in=ids).update(is_processed=True)
            messages.success(request, f"✅ {count} application(s) marked as processed.")
            return redirect('community:admin_tutor_application_list')
        elif ids and action == 'mark_unprocessed' and request.user.has_perm('community.change_tutorapplication'):
            count = TutorApplication.objects.filter(id__in=ids).update(is_processed=False)
            messages.success(request, f"✅ {count} application(s) marked as unprocessed.")
            return redirect('community:admin_tutor_application_list')

    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')

    applications = TutorApplication.objects.all().order_by('-submitted_at')
    if query:
        applications = applications.filter(
            Q(name__icontains=query) |
            Q(reg_number__icontains=query) |
            Q(email__icontains=query) |
            Q(department__icontains=query)
        )
    if status_filter == 'processed':
        applications = applications.filter(is_processed=True)
    elif status_filter == 'pending':
        applications = applications.filter(is_processed=False)

    paginator = Paginator(applications, 20)
    page = request.GET.get('page')
    applications_page = paginator.get_page(page)

    return render(request, 'community/admin/tutor_application_list.html', {
        'applications': applications_page,
        'page_obj': applications_page,
        'is_paginated': applications_page.has_other_pages(),
        'query': query,
        'status_filter': status_filter,
    })


@login_required
def admin_tutor_application_detail(request, pk):
    application = get_object_or_404(TutorApplication, pk=pk)
    if not request.user.has_perm('community.view_tutorapplication'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_tutor_application_list')

    return render(request, 'community/admin/tutor_application_detail.html', {
        'application': application,
    })


# ===== MEMBERSHIP APPLICATIONS ADMIN =====

@login_required
def admin_membership_application_list(request):
    if not request.user.has_perm('community.view_membershipapplication'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if ids and action == 'delete' and request.user.has_perm('community.delete_membershipapplication'):
            count = MembershipApplication.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} application(s) deleted.")
            return redirect('community:admin_membership_application_list')
        elif ids and action == 'mark_processed' and request.user.has_perm('community.change_membershipapplication'):
            count = MembershipApplication.objects.filter(id__in=ids).update(is_processed=True)
            messages.success(request, f"✅ {count} application(s) marked as processed.")
            return redirect('community:admin_membership_application_list')
        elif ids and action == 'mark_unprocessed' and request.user.has_perm('community.change_membershipapplication'):
            count = MembershipApplication.objects.filter(id__in=ids).update(is_processed=False)
            messages.success(request, f"✅ {count} application(s) marked as unprocessed.")
            return redirect('community:admin_membership_application_list')

    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')

    applications = MembershipApplication.objects.all().order_by('-submitted_at')
    if query:
        applications = applications.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(reg_number__icontains=query) |
            Q(department__icontains=query)
        )
    if status_filter == 'processed':
        applications = applications.filter(is_processed=True)
    elif status_filter == 'pending':
        applications = applications.filter(is_processed=False)

    paginator = Paginator(applications, 20)
    page = request.GET.get('page')
    applications_page = paginator.get_page(page)

    return render(request, 'community/admin/membership_application_list.html', {
        'applications': applications_page,
        'page_obj': applications_page,
        'is_paginated': applications_page.has_other_pages(),
        'query': query,
        'status_filter': status_filter,
    })


@login_required
def admin_membership_application_detail(request, pk):
    application = get_object_or_404(MembershipApplication, pk=pk)
    if not request.user.has_perm('community.view_membershipapplication'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_membership_application_list')

    return render(request, 'community/admin/membership_application_detail.html', {
        'application': application,
    })


# ===== SKILLS ADMIN =====

@login_required
def admin_skill_list(request):
    if not request.user.has_perm('community.view_skill'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if ids and action == 'delete' and request.user.has_perm('community.delete_skill'):
            count = Skill.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} skill(s) deleted.")
            return redirect('community:admin_skill_list')
        elif ids and action == 'activate' and request.user.has_perm('community.change_skill'):
            count = Skill.objects.filter(id__in=ids).update(is_active=True)
            messages.success(request, f"✅ {count} skill(s) activated.")
            return redirect('community:admin_skill_list')
        elif ids and action == 'deactivate' and request.user.has_perm('community.change_skill'):
            count = Skill.objects.filter(id__in=ids).update(is_active=False)
            messages.success(request, f"✅ {count} skill(s) deactivated.")
            return redirect('community:admin_skill_list')

    query = request.GET.get('q', '')
    skills = Skill.objects.all().order_by('name')
    if query:
        skills = skills.filter(name__icontains=query)

    paginator = Paginator(skills, 30)
    page = request.GET.get('page')
    skills_page = paginator.get_page(page)

    return render(request, 'community/admin/skill_list.html', {
        'skills': skills_page,
        'page_obj': skills_page,
        'is_paginated': skills_page.has_other_pages(),
        'query': query,
    })


@login_required
def admin_skill_create(request):
    if not request.user.has_perm('community.add_skill'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_skill_list')

    if request.method == 'POST':
        form = SkillForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Skill created.")
            return redirect('community:admin_skill_list')
    else:
        form = SkillForm()

    return render(request, 'community/admin/skill_form.html', {
        'form': form,
        'title': 'Add Skill',
        'button_text': 'Create Skill',
    })


@login_required
def admin_skill_edit(request, pk):
    skill = get_object_or_404(Skill, pk=pk)
    if not request.user.has_perm('community.change_skill'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_skill_list')

    if request.method == 'POST':
        form = SkillForm(request.POST, instance=skill)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Skill updated.")
            return redirect('community:admin_skill_list')
    else:
        form = SkillForm(instance=skill)

    return render(request, 'community/admin/skill_form.html', {
        'form': form,
        'skill': skill,
        'title': 'Edit Skill',
        'button_text': 'Update Skill',
    })


@login_required
def admin_skill_delete(request, pk):
    skill = get_object_or_404(Skill, pk=pk)
    if not request.user.has_perm('community.delete_skill'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_skill_list')

    if request.method == 'POST':
        name = skill.name
        skill.delete()
        messages.success(request, f"🗑️ Skill '{name}' deleted.")
        return redirect('community:admin_skill_list')

    return render(request, 'community/admin/skill_confirm_delete.html', {'skill': skill})


# ===== CONTACT PHONES ADMIN =====

@login_required
def admin_contact_phone_list(request):
    if not request.user.has_perm('community.view_contactphone'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if ids and action == 'delete' and request.user.has_perm('community.delete_contactphone'):
            count = ContactPhone.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} phone(s) deleted.")
            return redirect('community:admin_contact_phone_list')

    query = request.GET.get('q', '')
    phones = ContactPhone.objects.all().order_by('order')
    if query:
        phones = phones.filter(Q(label__icontains=query) | Q(phone_number__icontains=query))

    paginator = Paginator(phones, 30)
    page = request.GET.get('page')
    phones_page = paginator.get_page(page)

    return render(request, 'community/admin/contact_phone_list.html', {
        'phones': phones_page,
        'page_obj': phones_page,
        'is_paginated': phones_page.has_other_pages(),
        'query': query,
    })


@login_required
def admin_contact_phone_create(request):
    if not request.user.has_perm('community.add_contactphone'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_contact_phone_list')

    if request.method == 'POST':
        form = ContactPhoneForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Contact phone added.")
            return redirect('community:admin_contact_phone_list')
    else:
        form = ContactPhoneForm()

    return render(request, 'community/admin/contact_phone_form.html', {
        'form': form,
        'title': 'Add Contact Phone',
        'button_text': 'Add Phone',
    })


@login_required
def admin_contact_phone_edit(request, pk):
    phone = get_object_or_404(ContactPhone, pk=pk)
    if not request.user.has_perm('community.change_contactphone'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_contact_phone_list')

    if request.method == 'POST':
        form = ContactPhoneForm(request.POST, instance=phone)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Contact phone updated.")
            return redirect('community:admin_contact_phone_list')
    else:
        form = ContactPhoneForm(instance=phone)

    return render(request, 'community/admin/contact_phone_form.html', {
        'form': form,
        'phone': phone,
        'title': 'Edit Contact Phone',
        'button_text': 'Update Phone',
    })


@login_required
def admin_contact_phone_delete(request, pk):
    phone = get_object_or_404(ContactPhone, pk=pk)
    if not request.user.has_perm('community.delete_contactphone'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_contact_phone_list')

    if request.method == 'POST':
        label = phone.label
        phone.delete()
        messages.success(request, f"🗑️ Phone '{label}' deleted.")
        return redirect('community:admin_contact_phone_list')

    return render(request, 'community/admin/contact_phone_confirm_delete.html', {'phone': phone})


# ===== SOCIAL MEDIA LINKS ADMIN =====

@login_required
def admin_social_link_list(request):
    if not request.user.has_perm('community.view_socialmedialink'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if ids and action == 'delete' and request.user.has_perm('community.delete_socialmedialink'):
            count = SocialMediaLink.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} link(s) deleted.")
            return redirect('community:admin_social_link_list')
        elif ids and action == 'activate' and request.user.has_perm('community.change_socialmedialink'):
            count = SocialMediaLink.objects.filter(id__in=ids).update(is_active=True)
            messages.success(request, f"✅ {count} link(s) activated.")
            return redirect('community:admin_social_link_list')
        elif ids and action == 'deactivate' and request.user.has_perm('community.change_socialmedialink'):
            count = SocialMediaLink.objects.filter(id__in=ids).update(is_active=False)
            messages.success(request, f"✅ {count} link(s) deactivated.")
            return redirect('community:admin_social_link_list')

    query = request.GET.get('q', '')
    links = SocialMediaLink.objects.all().order_by('order')
    if query:
        links = links.filter(Q(platform__icontains=query) | Q(url__icontains=query))

    paginator = Paginator(links, 30)
    page = request.GET.get('page')
    links_page = paginator.get_page(page)

    return render(request, 'community/admin/social_link_list.html', {
        'links': links_page,
        'page_obj': links_page,
        'is_paginated': links_page.has_other_pages(),
        'query': query,
    })


@login_required
def admin_social_link_create(request):
    if not request.user.has_perm('community.add_socialmedialink'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_social_link_list')

    if request.method == 'POST':
        form = SocialMediaLinkForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Social media link added.")
            return redirect('community:admin_social_link_list')
    else:
        form = SocialMediaLinkForm()

    return render(request, 'community/admin/social_link_form.html', {
        'form': form,
        'title': 'Add Social Media Link',
        'button_text': 'Add Link',
    })


@login_required
def admin_social_link_edit(request, pk):
    link = get_object_or_404(SocialMediaLink, pk=pk)
    if not request.user.has_perm('community.change_socialmedialink'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_social_link_list')

    if request.method == 'POST':
        form = SocialMediaLinkForm(request.POST, instance=link)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Social media link updated.")
            return redirect('community:admin_social_link_list')
    else:
        form = SocialMediaLinkForm(instance=link)

    return render(request, 'community/admin/social_link_form.html', {
        'form': form,
        'link': link,
        'title': 'Edit Social Media Link',
        'button_text': 'Update Link',
    })


@login_required
def admin_social_link_delete(request, pk):
    link = get_object_or_404(SocialMediaLink, pk=pk)
    if not request.user.has_perm('community.delete_socialmedialink'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_social_link_list')

    if request.method == 'POST':
        platform = link.get_platform_display()
        link.delete()
        messages.success(request, f"🗑️ Link '{platform}' deleted.")
        return redirect('community:admin_social_link_list')

    return render(request, 'community/admin/social_link_confirm_delete.html', {'link': link})


# ===== NAMETS DOCUMENTS ADMIN =====

@login_required
def admin_document_list(request):
    if not request.user.has_perm('community.view_nametsdocument'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if ids and action == 'delete' and request.user.has_perm('community.delete_nametsdocument'):
            count = NAMETSDocument.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} document(s) deleted.")
            return redirect('community:admin_document_list')
        elif ids and action == 'activate' and request.user.has_perm('community.change_nametsdocument'):
            count = NAMETSDocument.objects.filter(id__in=ids).update(is_active=True)
            messages.success(request, f"✅ {count} document(s) activated.")
            return redirect('community:admin_document_list')
        elif ids and action == 'deactivate' and request.user.has_perm('community.change_nametsdocument'):
            count = NAMETSDocument.objects.filter(id__in=ids).update(is_active=False)
            messages.success(request, f"✅ {count} document(s) deactivated.")
            return redirect('community:admin_document_list')

    query = request.GET.get('q', '')
    documents = NAMETSDocument.objects.all().order_by('-uploaded_at')
    if query:
        documents = documents.filter(Q(title__icontains=query) | Q(description__icontains=query))

    paginator = Paginator(documents, 20)
    page = request.GET.get('page')
    documents_page = paginator.get_page(page)

    return render(request, 'community/admin/document_list.html', {
        'documents': documents_page,
        'page_obj': documents_page,
        'is_paginated': documents_page.has_other_pages(),
        'query': query,
    })


@login_required
def admin_document_create(request):
    if not request.user.has_perm('community.add_nametsdocument'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_document_list')

    if request.method == 'POST':
        form = NAMETSDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save()
            messages.success(request, f"✅ Document '{document.title}' uploaded.")
            return redirect('community:admin_document_list')
    else:
        form = NAMETSDocumentForm()

    return render(request, 'community/admin/document_form.html', {
        'form': form,
        'title': 'Upload Document',
        'button_text': 'Upload Document',
    })


@login_required
def admin_document_edit(request, pk):
    document = get_object_or_404(NAMETSDocument, pk=pk)
    if not request.user.has_perm('community.change_nametsdocument'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_document_list')

    if request.method == 'POST':
        form = NAMETSDocumentForm(request.POST, request.FILES, instance=document)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Document '{document.title}' updated.")
            return redirect('community:admin_document_list')
    else:
        form = NAMETSDocumentForm(instance=document)

    return render(request, 'community/admin/document_form.html', {
        'form': form,
        'document': document,
        'title': 'Edit Document',
        'button_text': 'Update Document',
    })


@login_required
def admin_document_delete(request, pk):
    document = get_object_or_404(NAMETSDocument, pk=pk)
    if not request.user.has_perm('community.delete_nametsdocument'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_document_list')

    if request.method == 'POST':
        title = document.title
        document.delete()
        messages.success(request, f"🗑️ Document '{title}' deleted.")
        return redirect('community:admin_document_list')

    return render(request, 'community/admin/document_confirm_delete.html', {'document': document})


# ===== TUTOR APPLICATION EDIT =====

@login_required
def admin_tutor_application_edit(request, pk):
    application = get_object_or_404(TutorApplication, pk=pk)
    if not request.user.has_perm('community.change_tutorapplication'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_tutor_application_list')

    if request.method == 'POST':
        form = TutorApplicationForm(request.POST, instance=application)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Application for '{application.name}' updated.")
            return redirect('community:admin_tutor_application_detail', pk=application.pk)
    else:
        form = TutorApplicationForm(instance=application)

    return render(request, 'community/admin/tutor_application_form.html', {
        'form': form,
        'application': application,
        'title': 'Edit Tutor Application',
        'button_text': 'Update Application',
    })


# ===== MEMBERSHIP APPLICATION EDIT =====

@login_required
def admin_membership_application_edit(request, pk):
    application = get_object_or_404(MembershipApplication, pk=pk)
    if not request.user.has_perm('community.change_membershipapplication'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_membership_application_list')

    if request.method == 'POST':
        form = MembershipApplicationForm(request.POST, instance=application)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Application for '{application.name}' updated.")
            return redirect('community:admin_membership_application_detail', pk=application.pk)
    else:
        form = MembershipApplicationForm(instance=application)

    return render(request, 'community/admin/membership_application_form.html', {
        'form': form,
        'application': application,
        'title': 'Edit Membership Application',
        'button_text': 'Update Application',
    })


@login_required
def admin_question_toggle(request, pk):
    question = get_object_or_404(Question, pk=pk)
    if not request.user.has_perm('community.change_question'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_question_list')
    question.is_public = not question.is_public
    question.save()
    status = "approved" if question.is_public else "unapproved"
    messages.success(request, f"✅ Question {status}.")
    return redirect('community:admin_question_list')


@login_required
def admin_question_delete(request, pk):
    """Delete a question."""
    question = get_object_or_404(Question, pk=pk)
    if not request.user.has_perm('community.delete_question'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_question_list')

    if request.method == 'POST':
        question.delete()
        messages.success(request, "🗑️ Question deleted.")
        return redirect('community:admin_question_list')

    return render(request, 'community/admin/question_confirm_delete.html', {'question': question})




@login_required
def admin_executive_toggle_public(request, pk):
    executive = get_object_or_404(Executive, pk=pk)
    if not request.user.has_perm('community.change_executive'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_executive_list')

    executive.show_on_public = not executive.show_on_public
    executive.save()
    status = "visible to the public" if executive.show_on_public else "hidden from the public"
    messages.success(request, f"✅ '{executive.name}' is now {status}.")
    return redirect('community:admin_executive_list')





from core.importers.excel_io import build_export_xlsx
from core.importers.spec import ColumnSpec, ImportSpec
from django.http import JsonResponse


@login_required
def admin_executive_export(request):
    if not request.user.has_perm('community.view_executive'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_executive_list')

    # Get filters from request
    year_filter = request.GET.get('year', '')
    status_filter = request.GET.get('status', '')
    query = request.GET.get('q', '')

    queryset = Executive.objects.select_related('year').all()

    if year_filter:
        queryset = queryset.filter(year_id=year_filter)
    if status_filter == 'active':
        queryset = queryset.filter(is_active=True)
    elif status_filter == 'inactive':
        queryset = queryset.filter(is_active=False)
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query) | Q(role__icontains=query)
        )

    # Build spec for export
    spec = ImportSpec()
    spec.key = 'executives_export'
    spec.label = 'Executives Export'
    spec.columns = [
        ColumnSpec('name', 'Name'),
        ColumnSpec('role', 'Role'),
        ColumnSpec('year_label', 'Year'),
        ColumnSpec('display_order', 'Display Order'),
        ColumnSpec('contribution_summary', 'Contribution Summary'),
        ColumnSpec('is_active', 'Active'),
    ]

    def row_from_instance(exec):
        return {
            'name': exec.name,
            'role': exec.role,
            'year_label': exec.year.year_label if exec.year else '',
            'display_order': exec.display_order,
            'contribution_summary': exec.contribution_summary,
            'is_active': 'Yes' if exec.is_active else 'No',
        }

    spec.export_queryset = lambda: queryset
    spec.row_from_instance = row_from_instance

    return build_export_xlsx(spec)


@login_required
def admin_executive_year_create_ajax(request):
    """AJAX endpoint to create a new ExecutiveYear from the form modal."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    if not request.user.has_perm('community.add_executiveyear'):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    year_label = request.POST.get('year_label', '').strip()
    description = request.POST.get('description', '').strip()
    display_order = request.POST.get('display_order', 0)

    if not year_label:
        return JsonResponse({'success': False, 'error': 'Year label is required.'})

    if ExecutiveYear.objects.filter(year_label__iexact=year_label).exists():
        return JsonResponse({'success': False, 'error': 'Year already exists.'})

    year = ExecutiveYear.objects.create(
        year_label=year_label,
        description=description,
        display_order=display_order,
        is_active=True,
    )

    return JsonResponse({
        'success': True,
        'year_id': year.id,
        'year_label': year.year_label,
    })


# ============================================================
# TUTOR APPLICATIONS — FULL ADMIN
# ============================================================

@login_required
def admin_tutor_application_list(request):
    if not request.user.has_perm('community.view_tutorapplication'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    # --- POST: Bulk actions ---
    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if not ids:
            messages.warning(request, "No items selected.")
            return redirect('community:admin_tutor_application_list')

        if action == 'delete' and request.user.has_perm('community.delete_tutorapplication'):
            count = TutorApplication.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} application(s) deleted.")

        elif action == 'mark_processed' and request.user.has_perm('community.change_tutorapplication'):
            count = TutorApplication.objects.filter(id__in=ids).update(is_processed=True)
            messages.success(request, f"✅ {count} application(s) marked as processed.")

        elif action == 'mark_unprocessed' and request.user.has_perm('community.change_tutorapplication'):
            count = TutorApplication.objects.filter(id__in=ids).update(is_processed=False)
            messages.success(request, f"✅ {count} application(s) marked as unprocessed.")

        elif action == 'send_email' and (request.user.has_perm('community.change_tutorapplication') or request.user.has_perm('communications.can_send_broadcast')):
            apps = TutorApplication.objects.filter(id__in=ids)
            emails = list(apps.values_list('email', flat=True))
            subject = request.POST.get('email_subject', '').strip()
            body = request.POST.get('email_body', '').strip()
            site_url = getattr(settings, 'SITE_BASE_URL', 'https://namets.org.ng')
            unsubscribe_url = f"{site_url}/unsubscribe/"

            if not subject or not body:
                messages.error(request, "Subject and body are required for email.")
            else:
                for email in emails:
                    send_templated_email(
                        subject=subject,
                        recipients=[email],
                        template_name='emails/tutor_app_broadcast.html',
                        context={
                            'subject': subject,
                            'body': body,
                        }
                    )
                messages.success(request, f"📧 Email sent to {len(emails)} applicant(s).")

        else:
            messages.error(request, "Invalid action or permission denied.")

        return redirect('community:admin_tutor_application_list')

    # --- GET: List with filters ---
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')

    applications = TutorApplication.objects.all().order_by('-submitted_at')
    if query:
        applications = applications.filter(
            Q(name__icontains=query) |
            Q(reg_number__icontains=query) |
            Q(email__icontains=query) |
            Q(department__icontains=query)
        )
    if status_filter == 'processed':
        applications = applications.filter(is_processed=True)
    elif status_filter == 'pending':
        applications = applications.filter(is_processed=False)

    paginator = Paginator(applications, 20)
    page = request.GET.get('page')
    applications_page = paginator.get_page(page)

    return render(request, 'community/admin/tutor_application_list.html', {
        'applications': applications_page,
        'page_obj': applications_page,
        'is_paginated': applications_page.has_other_pages(),
        'query': query,
        'status_filter': status_filter,
    })


@login_required
def admin_tutor_application_create(request):
    if not request.user.has_perm('community.add_tutorapplication'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_tutor_application_list')

    if request.method == 'POST':
        form = TutorApplicationForm(request.POST)
        if form.is_valid():
            app = form.save()
            messages.success(request, f"✅ Application for '{app.name}' created.")
            return redirect('community:admin_tutor_application_detail', pk=app.pk)
    else:
        form = TutorApplicationForm()

    return render(request, 'community/admin/tutor_application_form.html', {
        'form': form,
        'title': 'Add Tutor Application',
        'button_text': 'Create Application',
    })


@login_required
def admin_tutor_application_edit(request, pk):
    application = get_object_or_404(TutorApplication, pk=pk)
    if not request.user.has_perm('community.change_tutorapplication'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_tutor_application_list')

    if request.method == 'POST':
        form = TutorApplicationForm(request.POST, instance=application)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Application for '{application.name}' updated.")
            return redirect('community:admin_tutor_application_detail', pk=application.pk)
    else:
        form = TutorApplicationForm(instance=application)

    return render(request, 'community/admin/tutor_application_form.html', {
        'form': form,
        'application': application,
        'title': 'Edit Tutor Application',
        'button_text': 'Update Application',
    })


@login_required
def admin_tutor_application_detail(request, pk):
    application = get_object_or_404(TutorApplication, pk=pk)
    if not request.user.has_perm('community.view_tutorapplication'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_tutor_application_list')

    return render(request, 'community/admin/tutor_application_detail.html', {
        'application': application,
    })


@login_required
def admin_tutor_application_delete(request, pk):
    application = get_object_or_404(TutorApplication, pk=pk)
    if not request.user.has_perm('community.delete_tutorapplication'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_tutor_application_list')

    if request.method == 'POST':
        name = application.name
        application.delete()
        messages.success(request, f"🗑️ Application for '{name}' deleted.")
        return redirect('community:admin_tutor_application_list')

    return render(request, 'community/admin/tutor_application_confirm_delete.html', {
        'application': application,
    })


@login_required
def admin_tutor_application_export(request):
    if not request.user.has_perm('community.view_tutorapplication'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_tutor_application_list')

    from core.importers.spec import ColumnSpec, ImportSpec
    from core.importers.excel_io import build_export_xlsx

    spec = ImportSpec()
    spec.key = 'tutor_applications'
    spec.label = 'Tutor Applications'
    spec.columns = [
        ColumnSpec('name', 'Name'),
        ColumnSpec('reg_number', 'Reg Number'),
        ColumnSpec('department', 'Department'),
        ColumnSpec('cgpa', 'CGPA'),
        ColumnSpec('email', 'Email'),
        ColumnSpec('phone', 'Phone'),
        ColumnSpec('preferred_course', 'Preferred Course'),
        ColumnSpec('is_processed', 'Processed'),
        ColumnSpec('submitted_at', 'Submitted At'),
    ]

    def qs():
        return TutorApplication.objects.all().order_by('-submitted_at')

    def row(instance):
        return {
            'name': instance.name,
            'reg_number': instance.reg_number,
            'department': instance.department,
            'cgpa': instance.cgpa,
            'email': instance.email,
            'phone': instance.phone,
            'preferred_course': instance.preferred_course,
            'is_processed': 'Yes' if instance.is_processed else 'No',
            'submitted_at': instance.submitted_at.strftime('%Y-%m-%d %H:%M'),
        }

    spec.export_queryset = qs
    spec.row_from_instance = row
    return build_export_xlsx(spec)


# ============================================================
# MEMBERSHIP APPLICATIONS — FULL ADMIN
# ============================================================

@login_required
def admin_membership_application_list(request):
    if not request.user.has_perm('community.view_membershipapplication'):
        messages.error(request, "Permission denied.")
        return redirect('dashboards:dashboard')

    # --- POST: Bulk actions ---
    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if not ids:
            messages.warning(request, "No items selected.")
            return redirect('community:admin_membership_application_list')

        if action == 'delete' and request.user.has_perm('community.delete_membershipapplication'):
            count = MembershipApplication.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} application(s) deleted.")

        elif action == 'mark_processed' and request.user.has_perm('community.change_membershipapplication'):
            count = MembershipApplication.objects.filter(id__in=ids).update(is_processed=True)
            messages.success(request, f"✅ {count} application(s) marked as processed.")

        elif action == 'mark_unprocessed' and request.user.has_perm('community.change_membershipapplication'):
            count = MembershipApplication.objects.filter(id__in=ids).update(is_processed=False)
            messages.success(request, f"✅ {count} application(s) marked as unprocessed.")

        elif action == 'send_email' and (request.user.has_perm('community.change_membershipapplication') or request.user.has_perm('communications.can_send_broadcast')):
            apps = MembershipApplication.objects.filter(id__in=ids)
            emails = list(apps.values_list('email', flat=True))
            subject = request.POST.get('email_subject', '').strip()
            body = request.POST.get('email_body', '').strip()
            site_url = getattr(settings, 'SITE_BASE_URL', 'https://namets.org.ng')
            unsubscribe_url = f"{site_url}/unsubscribe/"

            if not subject or not body:
                messages.error(request, "Subject and body are required for email.")
            else:
                for email in emails:
                    send_templated_email(
                        subject=subject,
                        recipients=[email],
                        template_name='emails/membership_app_broadcast.html',
                        context={
                            'subject': subject,
                            'body': body,
                        }
                    )
                messages.success(request, f"📧 Email sent to {len(emails)} applicant(s).")

        else:
            messages.error(request, "Invalid action or permission denied.")

        return redirect('community:admin_membership_application_list')

    # --- GET: List with filters ---
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')

    applications = MembershipApplication.objects.all().order_by('-submitted_at')
    if query:
        applications = applications.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(reg_number__icontains=query) |
            Q(department__icontains=query)
        )
    if status_filter == 'processed':
        applications = applications.filter(is_processed=True)
    elif status_filter == 'pending':
        applications = applications.filter(is_processed=False)

    paginator = Paginator(applications, 20)
    page = request.GET.get('page')
    applications_page = paginator.get_page(page)

    return render(request, 'community/admin/membership_application_list.html', {
        'applications': applications_page,
        'page_obj': applications_page,
        'is_paginated': applications_page.has_other_pages(),
        'query': query,
        'status_filter': status_filter,
    })


@login_required
def admin_membership_application_create(request):
    if not request.user.has_perm('community.add_membershipapplication'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_membership_application_list')

    if request.method == 'POST':
        form = MembershipApplicationForm(request.POST)
        if form.is_valid():
            app = form.save()
            messages.success(request, f"✅ Application for '{app.name}' created.")
            return redirect('community:admin_membership_application_detail', pk=app.pk)
    else:
        form = MembershipApplicationForm()

    return render(request, 'community/admin/membership_application_form.html', {
        'form': form,
        'title': 'Add Membership Application',
        'button_text': 'Create Application',
    })


@login_required
def admin_membership_application_edit(request, pk):
    application = get_object_or_404(MembershipApplication, pk=pk)
    if not request.user.has_perm('community.change_membershipapplication'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_membership_application_list')

    if request.method == 'POST':
        form = MembershipApplicationForm(request.POST, instance=application)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Application for '{application.name}' updated.")
            return redirect('community:admin_membership_application_detail', pk=application.pk)
    else:
        form = MembershipApplicationForm(instance=application)

    return render(request, 'community/admin/membership_application_form.html', {
        'form': form,
        'application': application,
        'title': 'Edit Membership Application',
        'button_text': 'Update Application',
    })


@login_required
def admin_membership_application_detail(request, pk):
    application = get_object_or_404(MembershipApplication, pk=pk)
    if not request.user.has_perm('community.view_membershipapplication'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_membership_application_list')

    return render(request, 'community/admin/membership_application_detail.html', {
        'application': application,
    })


@login_required
def admin_membership_application_delete(request, pk):
    application = get_object_or_404(MembershipApplication, pk=pk)
    if not request.user.has_perm('community.delete_membershipapplication'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_membership_application_list')

    if request.method == 'POST':
        name = application.name
        application.delete()
        messages.success(request, f"🗑️ Application for '{name}' deleted.")
        return redirect('community:admin_membership_application_list')

    return render(request, 'community/admin/membership_application_confirm_delete.html', {
        'application': application,
    })


@login_required
def admin_membership_application_export(request):
    if not request.user.has_perm('community.view_membershipapplication'):
        messages.error(request, "Permission denied.")
        return redirect('community:admin_membership_application_list')

    from core.importers.spec import ColumnSpec, ImportSpec
    from core.importers.excel_io import build_export_xlsx

    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')

    queryset = MembershipApplication.objects.all().order_by('-submitted_at')
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(reg_number__icontains=query)
        )
    if status_filter == 'processed':
        queryset = queryset.filter(is_processed=True)
    elif status_filter == 'pending':
        queryset = queryset.filter(is_processed=False)

    spec = ImportSpec()
    spec.key = 'membership_applications'
    spec.label = 'Membership Applications'
    spec.columns = [
        ColumnSpec('name', 'Name'),
        ColumnSpec('email', 'Email'),
        ColumnSpec('phone', 'Phone'),
        ColumnSpec('gender', 'Gender'),
        ColumnSpec('reg_number', 'Reg Number'),
        ColumnSpec('department', 'Department'),
        ColumnSpec('campus_residence', 'Campus Residence'),
        ColumnSpec('islamic_knowledge', 'Islamic Knowledge'),
        ColumnSpec('quran_memorization', 'Quran Memorization'),
        ColumnSpec('is_processed', 'Processed'),
        ColumnSpec('submitted_at', 'Submitted At'),
    ]

    def row_from_instance(app):
        return {
            'name': app.name,
            'email': app.email,
            'phone': app.phone,
            'gender': app.get_gender_display(),
            'reg_number': app.reg_number,
            'department': app.department,
            'campus_residence': 'Yes' if app.campus_residence else 'No',
            'islamic_knowledge': app.get_islamic_knowledge_display(),
            'quran_memorization': app.get_quran_memorization_display(),
            'is_processed': 'Yes' if app.is_processed else 'No',
            'submitted_at': app.submitted_at.strftime('%Y-%m-%d %H:%M'),
        }

    spec.export_queryset = lambda: queryset
    spec.row_from_instance = row_from_instance
    return build_export_xlsx(spec)


