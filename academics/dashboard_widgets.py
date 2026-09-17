from core.dashboard_widgets import DashboardWidget, register_widget
from .models import (
    IslamiyyaRegistration, UserResourceSubmission,
    IslamiyyaSettings, Course, TutorEvaluation,
)


# ============================================================
# ISLAMIYYA — PENDING PAYMENTS
# ============================================================

class IslamiyyaPendingWidget(DashboardWidget):
    permission = "academics.view_islamiyyaregistration"
    label = "Islamiyya Pending Payments"
    icon = "fa-mosque"
    url_name = "academics:admin_islamiyya_verification_queue"

    def get_count(self):
        return IslamiyyaRegistration.objects.filter(payment_status='pending').count()


# ============================================================
# ISLAMIYYA — TOTAL PAID (this session)
# ============================================================

class IslamiyyaPaidWidget(DashboardWidget):
    permission = "academics.view_islamiyyaregistration"
    label = "Islamiyya Paid"
    icon = "fa-check-circle"
    url_name = "academics:admin_islamiyya_registration_list"

    def get_count(self):
        return IslamiyyaRegistration.objects.filter(payment_status='paid').count()


# ============================================================
# RESOURCE SUBMISSIONS
# ============================================================

class ResourcePendingWidget(DashboardWidget):
    permission = "academics.view_userresourcesubmission"
    label = "Pending Resource Submissions"
    icon = "fa-file-upload"
    url_name = "academics:admin_resource_list"

    def get_count(self):
        return UserResourceSubmission.objects.filter(status='pending').count()


# ============================================================
# ACTIVE COURSES
# ============================================================

class ActiveCoursesWidget(DashboardWidget):
    permission = "academics.view_course"
    label = "Active Courses"
    icon = "fa-book"
    url_name = "academics:admin_course_list"

    def get_count(self):
        return Course.objects.filter(is_active=True).count()


# ============================================================
# TUTOR EVALUATIONS (this session)
# ============================================================

class TutorEvaluationsWidget(DashboardWidget):
    permission = "academics.view_tutorevaluation"
    label = "Tutor Evaluations"
    icon = "fa-star"
    url_name = "academics:admin_tutor_evaluation_list"

    def get_count(self):
        return TutorEvaluation.objects.count()


# ============================================================
# REGISTER ALL
# ============================================================

register_widget(IslamiyyaPendingWidget())
register_widget(IslamiyyaPaidWidget())
register_widget(ResourcePendingWidget())
register_widget(ActiveCoursesWidget())
register_widget(TutorEvaluationsWidget())