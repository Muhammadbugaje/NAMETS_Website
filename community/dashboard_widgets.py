from core.dashboard_widgets import DashboardWidget, register_widget
from .models import MembershipApplication, TutorApplication, Question

class MembershipPendingWidget(DashboardWidget):
    permission = "community.view_membershipapplication"
    label = "Membership Applications"
    icon = "fa-user-plus"
    url_name = "admin:community_membershipapplication_changelist"

    def get_count(self):
        return MembershipApplication.objects.filter(is_processed=False).count()

class TutorPendingWidget(DashboardWidget):
    permission = "community.view_tutorapplication"
    label = "Tutor Applications"
    icon = "fa-chalkboard-teacher"
    url_name = "admin:community_tutorapplication_changelist"

    def get_count(self):
        return TutorApplication.objects.filter(is_processed=False).count()

class QAPendingWidget(DashboardWidget):
    permission = "community.view_question"
    label = "Private Q&A Questions"
    icon = "fa-question-circle"
    url_name = "admin:community_question_changelist"

    def get_count(self):
        return Question.objects.filter(is_public=False).count()

register_widget(MembershipPendingWidget())
register_widget(TutorPendingWidget())
register_widget(QAPendingWidget())