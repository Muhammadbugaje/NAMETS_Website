from .models import Patron, ExecutiveYear, Executive, Developer, Question, Answer, AboutPage

def get_active_patrons():
    return Patron.objects.filter(is_active=True)

def get_executive_years():
    return ExecutiveYear.objects.filter(is_active=True)

def get_executives_by_year(year_id=None):
    qs = Executive.objects.filter(is_active=True).select_related('year')
    if year_id:
        qs = qs.filter(year_id=year_id)
    return qs

def get_active_developers():
    return Developer.objects.filter(is_active=True)

def get_about_info():
    return AboutPage.objects.first()


def get_featured_patron():
    """Return a featured patron (first active by hierarchy)."""
    from .models import Patron
    return Patron.objects.filter(is_active=True).order_by('hierarchy_order').first()

def get_executives_for_current_year():
    """Return executives for the current active year."""
    current_year = ExecutiveYear.objects.filter(is_active=True).first()
    if current_year:
        return Executive.objects.filter(year=current_year, is_active=True).select_related('year').order_by('hierarchy_order')
    return Executive.objects.none()

def get_public_questions():
    """Return public questions with their answers."""
    return Question.objects.filter(is_public=True, answer__isnull=False).select_related('answer').order_by('-submitted_at')

def get_public_questions_with_answers():
    """Return public questions with their answers."""
    return Question.objects.filter(is_public=True, answer__isnull=False).select_related('answer').order_by('-submitted_at')