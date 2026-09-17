from django.urls import path
from . import views
from . import cbt_views

app_name = 'academics'

urlpatterns = [
    # ============================================================
    # PUBLIC ROUTES (all existing — unchanged)
    # ============================================================
    path('', views.course_list, name='course_list'),
    path('tutorials/', views.tutorial_list, name='tutorial_list'),
    path('islamiyya/', views.islamia_list, name='islamia_list'),
    path('courses/<slug:slug>/', views.course_detail, name='course_detail'),
    path('courses/<slug:slug>/results/', views.course_results, name='course_results'),
    path('courses/<slug:slug>/evaluate/', views.evaluate_tutor, name='evaluate_tutor'),
    path('students/search/', views.student_search, name='student_search'),
    path('courses/<slug:slug>/materials/', views.materials_list, name='materials_list'),
    path('courses/<slug:slug>/exams/', views.exam_list, name='exams_list'),
    path('exams/', views.exam_list, name='exam_list'),
    path('exams/<int:exam_id>/', views.exam_detail, name='exam_detail'),
    path('results/', views.all_results, name='all_results'),
    path('material/<int:material_id>/download/', views.download_material, name='download_material'),

    # ---------- ISLAMIYYA PUBLIC ----------
    path('islamiyya/register/', views.islamiyya_register, name='islamiyya_register'),
    path('islamiyya/status/', views.islamiyya_check_status, name='islamiyya_check_status'),
    path('islamiyya/dashboard/', views.islamiyya_dashboard, name='islamiyya_dashboard'),
    path('islamiyya/<str:app_id>/pay/', views.islamiyya_pay, name='islamiyya_pay'),
    path('islamiyya/paystack-callback/', views.islamiyya_paystack_callback, name='islamiyya_paystack_callback'),

    # ---------- RESOURCES ----------
    path('resources/', views.resources_page, name='resources'),
    path('submit-resource/', views.submit_resource, name='submit_resource'),
    path('download/<int:pk>/', views.download_resource, name='download_resource'),

    # ---------- COMPETITION RESULTS ----------
    path('competition-results/', views.competition_results, name='competition_results'),

    # ============================================================
    # EXCO ADMIN ROUTES
    # ============================================================

    # ---------- DASHBOARD ----------
    path('admin/', views.admin_dashboard, name='admin_dashboard'),

    # ---------- SETTINGS ----------
    path('admin/settings/', views.admin_academics_settings, name='admin_academics_settings'),

    # ---------- COURSES ----------
    path('admin/courses/', views.admin_course_list, name='admin_course_list'),
    path('admin/courses/create/', views.admin_course_create, name='admin_course_create'),
    path('admin/courses/<int:pk>/edit/', views.admin_course_edit, name='admin_course_edit'),
    path('admin/courses/<int:pk>/delete/', views.admin_course_delete, name='admin_course_delete'),

    # ---------- TUTORS ----------
    path('admin/tutors/', views.admin_tutor_list, name='admin_tutor_list'),
    path('admin/tutors/create/', views.admin_tutor_create, name='admin_tutor_create'),
    path('admin/tutors/<int:pk>/edit/', views.admin_tutor_edit, name='admin_tutor_edit'),
    path('admin/tutors/<int:pk>/delete/', views.admin_tutor_delete, name='admin_tutor_delete'),

    # ---------- SESSIONS ----------
    path('admin/sessions/', views.admin_session_list, name='admin_session_list'),
    path('admin/sessions/create/', views.admin_session_create, name='admin_session_create'),
    path('admin/sessions/<int:pk>/edit/', views.admin_session_edit, name='admin_session_edit'),
    path('admin/sessions/<int:pk>/delete/', views.admin_session_delete, name='admin_session_delete'),

    # ---------- MATERIALS ----------
    path('admin/materials/', views.admin_material_list, name='admin_material_list'),
    path('admin/materials/create/', views.admin_material_create, name='admin_material_create'),
    path('admin/materials/<int:pk>/edit/', views.admin_material_edit, name='admin_material_edit'),
    path('admin/materials/<int:pk>/delete/', views.admin_material_delete, name='admin_material_delete'),

    # ---------- EVALUATIONS (EXAMS) ----------
    path('admin/evaluations/', views.admin_evaluation_list, name='admin_evaluation_list'),
    path('admin/evaluations/create/', views.admin_evaluation_create, name='admin_evaluation_create'),
    path('admin/evaluations/<int:pk>/edit/', views.admin_evaluation_edit, name='admin_evaluation_edit'),
    path('admin/evaluations/<int:pk>/delete/', views.admin_evaluation_delete, name='admin_evaluation_delete'),
    path('admin/evaluations/<int:pk>/upload-results/', views.admin_evaluation_upload_results, name='admin_evaluation_upload_results'),

    # ---------- RESULTS ----------
    path('admin/results/', views.admin_result_list, name='admin_result_list'),
    path('admin/results/<int:pk>/delete/', views.admin_result_delete, name='admin_result_delete'),

    path('admin/results/<int:pk>/edit/', views.admin_result_edit, name='admin_result_edit'),
    path('admin/results/export/', views.admin_result_export, name='admin_result_export'),
    path('admin/attendance/report/', views.admin_attendance_report, name='admin_attendance_report'),


    # ---------- TIMETABLE ----------
    path('admin/timetable/', views.admin_timetable_list, name='admin_timetable_list'),
    path('admin/timetable/create/', views.admin_timetable_create, name='admin_timetable_create'),
    path('admin/timetable/<int:pk>/edit/', views.admin_timetable_edit, name='admin_timetable_edit'),
    path('admin/timetable/<int:pk>/delete/', views.admin_timetable_delete, name='admin_timetable_delete'),

    # ---------- ISLAMIYYA COURSES ----------
    path('admin/islamiyya-courses/', views.admin_islamiyya_course_list, name='admin_islamiyya_course_list'),
    path('admin/islamiyya-courses/create/', views.admin_islamiyya_course_create, name='admin_islamiyya_course_create'),
    path('admin/islamiyya-courses/<int:pk>/edit/', views.admin_islamiyya_course_edit, name='admin_islamiyya_course_edit'),
    path('admin/islamiyya-courses/<int:pk>/delete/', views.admin_islamiyya_course_delete, name='admin_islamiyya_course_delete'),

    # ---------- ISLAMIYYA SETTINGS (per-session) ----------
    path('admin/islamiyya-settings/', views.admin_islamiyya_settings_list, name='admin_islamiyya_settings_list'),
    path('admin/islamiyya-settings/create/', views.admin_islamiyya_settings_create, name='admin_islamiyya_settings_create'),
    path('admin/islamiyya-settings/<int:pk>/edit/', views.admin_islamiyya_settings_edit, name='admin_islamiyya_settings_edit'),
    path('admin/islamiyya-settings/<int:pk>/delete/', views.admin_islamiyya_settings_delete, name='admin_islamiyya_settings_delete'),
    path('admin/islamiyya-settings/<int:pk>/activate/', views.admin_islamiyya_settings_activate, name='admin_islamiyya_settings_activate'),
    path('admin/islamiyya-settings/<int:pk>/toggle-open/', views.admin_islamiyya_settings_toggle_open, name='admin_islamiyya_settings_toggle_open'),

    # ---------- ISLAMIYYA REGISTRATIONS ----------
    path('admin/islamiyya/', views.admin_islamiyya_registration_list, name='admin_islamiyya_registration_list'),
    path('admin/islamiyya/queue/', views.admin_islamiyya_verification_queue, name='admin_islamiyya_verification_queue'),
    path('admin/islamiyya/analytics/', views.admin_islamiyya_analytics, name='admin_islamiyya_analytics'),
    path('admin/islamiyya/export/', views.admin_islamiyya_registration_export, name='admin_islamiyya_registration_export'),
    path('admin/islamiyya/<int:pk>/', views.admin_islamiyya_registration_detail, name='admin_islamiyya_registration_detail'),
    path('admin/islamiyya/<int:pk>/edit/', views.admin_islamiyya_registration_edit, name='admin_islamiyya_registration_edit'),
    path('admin/islamiyya/<int:pk>/delete/', views.admin_islamiyya_registration_delete, name='admin_islamiyya_registration_delete'),
    path('admin/islamiyya/<int:pk>/mark-paid/', views.admin_islamiyya_registration_mark_paid, name='admin_islamiyya_registration_mark_paid'),
    path('admin/islamiyya/<int:pk>/waive/', views.admin_islamiyya_registration_waive, name='admin_islamiyya_registration_waive'),
    path('admin/islamiyya/<int:pk>/refund/', views.admin_islamiyya_registration_refund, name='admin_islamiyya_registration_refund'),
    path('admin/islamiyya/<int:pk>/issue-certificate/', views.admin_islamiyya_registration_issue_certificate, name='admin_islamiyya_registration_issue_certificate'),
    path('admin/islamiyya/<int:pk>/send-whatsapp/', views.admin_islamiyya_send_whatsapp_link, name='admin_islamiyya_send_whatsapp'),
    path('islamiyya/<str:app_id>/pay/manual/', views.islamiyya_choose_manual_payment, name='islamiyya_payment_manual'),
    path('islamiyya/slip/<str:app_id>/', views.islamiyya_slip, name='islamiyya_slip'),

    # Bulk actions
    path('admin/islamiyya/bulk/mark-paid/', views.admin_islamiyya_bulk_mark_paid, name='admin_islamiyya_bulk_mark_paid'),
    path('admin/islamiyya/bulk/waive/', views.admin_islamiyya_bulk_waive, name='admin_islamiyya_bulk_waive'),
    path('admin/islamiyya/bulk/refund/', views.admin_islamiyya_bulk_refund, name='admin_islamiyya_bulk_refund'),
    path('admin/islamiyya/bulk/issue-certificate/', views.admin_islamiyya_bulk_issue_certificate, name='admin_islamiyya_bulk_issue_certificate'),

    # ---------- RESOURCES ----------
    path('admin/resources/', views.admin_resource_list, name='admin_resource_list'),
    path('admin/resources/<int:pk>/review/', views.admin_resource_review, name='admin_resource_review'),
    path('admin/resources/<int:pk>/approve/', views.admin_resource_approve, name='admin_resource_approve'),
    path('admin/resources/<int:pk>/reject/', views.admin_resource_reject, name='admin_resource_reject'),
    path('admin/resources/<int:pk>/delete/', views.admin_resource_delete, name='admin_resource_delete'),

    # ---------- TUTOR EVALUATIONS ----------
    path('admin/tutor-evaluations/', views.admin_tutor_evaluation_list, name='admin_tutor_evaluation_list'),
    path('admin/tutor-evaluations/export/', views.admin_tutor_evaluation_export, name='admin_tutor_evaluation_export'),

    # ---------- COMPETITION RESULTS ----------
    path('admin/competition/', views.admin_competition_list, name='admin_competition_list'),
    path('admin/competition/create/', views.admin_competition_create, name='admin_competition_create'),
    path('admin/competition/<int:pk>/edit/', views.admin_competition_edit, name='admin_competition_edit'),
    path('admin/competition/<int:pk>/delete/', views.admin_competition_delete, name='admin_competition_delete'),
    path('admin/competition/upload/', views.admin_competition_upload, name='admin_competition_upload'),

    # ---------- ATTENDANCE ----------
    path('admin/attendance/', views.admin_attendance_list, name='admin_attendance_list'),
    path('admin/attendance/create/', views.admin_attendance_create, name='admin_attendance_create'),
    path('admin/attendance/<int:pk>/edit/', views.admin_attendance_edit, name='admin_attendance_edit'),
    path('admin/attendance/<int:pk>/delete/', views.admin_attendance_delete, name='admin_attendance_delete'),
    path('admin/attendance/report/', views.admin_attendance_report, name='admin_attendance_report'),

    # ---------- COURSES ----------
    path('admin/courses/import/', views.admin_course_import, name='admin_course_import'),
    path('admin/courses/export/', views.admin_course_export, name='admin_course_export'),

    # ---------- TUTORS ----------
    path('admin/tutors/import/', views.admin_tutor_import, name='admin_tutor_import'),
    path('admin/tutors/export/', views.admin_tutor_export, name='admin_tutor_export'),

    # ---------- RESULTS ----------
    path('admin/results/import/', views.admin_result_import, name='admin_result_import'),
    # (export URL already exists)

    # ---------- ISLAMIYYA REGISTRATIONS ----------
    path('admin/islamiyya/import/', views.admin_islamiyya_registration_import, name='admin_islamiyya_registration_import'),

    # ---------- COMPETITION ----------
    path('admin/competition/export/', views.admin_competition_export, name='admin_competition_export'),

    # ---------- RESOURCE ADD ----------
    path('admin/resources/add/', views.admin_resource_create, name='admin_resource_create'),

    # ---------- ATTENDANCE ----------
    path('admin/attendance/import/', views.admin_attendance_import, name='admin_attendance_import'),  # optional global import
    path('admin/attendance/export/', views.admin_attendance_export, name='admin_attendance_export'),
    path('admin/attendance/<int:pk>/session-export/', views.admin_attendance_session_export, name='admin_attendance_session_export'),
    path('admin/attendance/<int:pk>/session-import/', views.admin_attendance_session_import, name='admin_attendance_session_import'),


    # ============================================================
    # ==================== CBT (ADMIN / EXCO) ====================
    # ============================================================
    path('admin/cbt/', cbt_views.admin_cbt_dashboard, name='admin_cbt_dashboard'),
    path('admin/cbt/courses/', cbt_views.admin_cbt_course_list, name='admin_cbt_course_list'),
    path('admin/cbt/courses/create/', cbt_views.admin_cbt_course_create, name='admin_cbt_course_create'),
    path('admin/cbt/courses/<int:pk>/edit/', cbt_views.admin_cbt_course_edit, name='admin_cbt_course_edit'),
    path('admin/cbt/courses/<int:pk>/delete/', cbt_views.admin_cbt_course_delete, name='admin_cbt_course_delete'),
    path('admin/cbt/courses/<int:pk>/toggle/', cbt_views.admin_cbt_course_toggle, name='admin_cbt_course_toggle'),

    path('admin/cbt/questions/', cbt_views.admin_question_list, name='admin_question_list'),
    path('admin/cbt/questions/create/', cbt_views.admin_question_create, name='admin_question_create'),
    path('admin/cbt/questions/template/', cbt_views.admin_question_sample_template, name='admin_question_sample_template'),
    path('admin/cbt/questions/export/', cbt_views.admin_question_export, name='admin_question_export'),
    path('admin/cbt/questions/import/', cbt_views.admin_question_import, name='admin_question_import'),
    path('admin/cbt/questions/bulk/', cbt_views.admin_question_bulk_action, name='admin_question_bulk_action'),
    path('admin/cbt/questions/<int:pk>/edit/', cbt_views.admin_question_edit, name='admin_question_edit'),
    path('admin/cbt/questions/<int:pk>/delete/', cbt_views.admin_question_delete, name='admin_question_delete'),
    path('admin/cbt/questions/<int:pk>/toggle/', cbt_views.admin_question_toggle, name='admin_question_toggle'),

    # ============================================================
    # ==================== CBT (PUBLIC / STUDENT) ================
    # ============================================================
    path('cbt/', cbt_views.cbt_home, name='cbt_home'),
    path('cbt/setup/', cbt_views.cbt_setup, name='cbt_setup'),
    path('cbt/start/', cbt_views.cbt_start, name='cbt_start'),
    path('cbt/pretest/', cbt_views.cbt_pretest, name='cbt_pretest'),
    path('cbt/take/', cbt_views.cbt_take, name='cbt_take'),
    path('cbt/submit/', cbt_views.cbt_submit, name='cbt_submit'),
    path('cbt/result/', cbt_views.cbt_result, name='cbt_result'),
    path('cbt/ai-report/', cbt_views.cbt_ai_report, name='cbt_ai_report'),
    path('cbt/retake/', cbt_views.cbt_retake, name='cbt_retake'),
    path('cbt/tab-switch/', cbt_views.cbt_tab_switch_ping, name='cbt_tab_switch_ping'),


    # ============================================================
    # LIBRARY (e-library — browse & download)
    # ============================================================
    path('library/', views.library_home, name='library_home'),
    path('library/<int:pk>/', views.library_book_detail, name='library_detail'),

    # Manage (staff / EXCO)
    path('library/manage/', views.library_manage, name='library_manage'),
    path('library/manage/new/', views.library_book_form, name='library_book_create'),
    path('library/manage/<int:pk>/edit/', views.library_book_form, name='library_book_edit'),
    path('library/manage/<int:pk>/delete/', views.library_book_delete, name='library_book_delete'),
    path('library/manage/categories/', views.library_category_manage, name='library_category_manage'),

    # ============================================================
    # CBT ANTI-CHEATING
    # ============================================================
    path('cbt/log-violation/', views.cbt_log_violation, name='cbt_log_violation'),



]

