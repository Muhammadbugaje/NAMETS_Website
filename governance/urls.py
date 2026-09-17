from django.urls import path

from . import views

app_name = 'governance'

urlpatterns = [
    # ============================================================
    # DASHBOARD
    # ============================================================
    path('', views.governance_dashboard, name='dashboard'),

    # ============================================================
    # TASKS
    # ============================================================
    path('tasks/', views.task_list, name='task_list'),
    path('tasks/create/', views.task_create, name='task_create'),
    path('tasks/<int:pk>/', views.task_detail, name='task_detail'),
    path('tasks/<int:pk>/edit/', views.task_edit, name='task_edit'),
    path('tasks/<int:pk>/delete/', views.task_delete, name='task_delete'),
    path('tasks/<int:pk>/complete/', views.task_mark_complete, name='task_mark_complete'),
    path('tasks/bulk/', views.task_bulk_action, name='task_bulk_action'),

    # ============================================================
    # PROPOSALS & VOTING
    # ============================================================
    path('proposals/', views.proposal_list, name='proposal_list'),
    path('proposals/create/', views.proposal_create, name='proposal_create'),
    path('proposals/<int:pk>/', views.proposal_detail, name='proposal_detail'),
    path('proposals/<int:pk>/edit/', views.proposal_edit, name='proposal_edit'),
    path('proposals/<int:pk>/delete/', views.proposal_delete, name='proposal_delete'),
    path('proposals/<int:pk>/open-voting/', views.proposal_open_voting, name='proposal_open_voting'),
    path('proposals/<int:pk>/close/', views.proposal_close, name='proposal_close'),
    path('proposals/<int:pk>/cancel/', views.proposal_cancel, name='proposal_cancel'),
    path('proposals/<int:pk>/vote/', views.vote_cast, name='vote_cast'),

    # ============================================================
    # AUDIT LOG
    # ============================================================
    path('audit/', views.audit_list, name='audit_list'),
    path('audit/<int:pk>/', views.audit_detail, name='audit_detail'),
    path('audit/export/', views.audit_export, name='audit_export'),

    # ============================================================
    # NOMINATIONS
    # ============================================================
    path('nominations/', views.nomination_list, name='nomination_list'),
    path('nominations/create/', views.nomination_create, name='nomination_create'),
    path('nominations/<int:pk>/edit/', views.nomination_edit, name='nomination_edit'),
    path('nominations/<int:pk>/status/', views.nomination_set_status, name='nomination_set_status'),
    path('nominations/<int:pk>/delete/', views.nomination_delete, name='nomination_delete'),

    # ============================================================
    # SELECTION RECORDS
    # ============================================================
    path('selections/', views.selection_list, name='selection_list'),
    path('selections/create/', views.selection_create, name='selection_create'),
    path('selections/<int:pk>/', views.selection_detail, name='selection_detail'),
    path('selections/<int:pk>/publish/', views.selection_publish, name='selection_publish'),
    path('selections/<int:pk>/delete/', views.selection_delete, name='selection_delete'),

    # ============================================================
    # OATH ACKNOWLEDGMENTS
    # ============================================================
    path('oaths/', views.oath_list, name='oath_list'),
    path('oaths/record/', views.oath_record, name='oath_record'),

    # ============================================================
    # HANDOVER
    # ============================================================
    path('handover/', views.handover_confirm, name='handover_confirm'),
    path('handover/execute/', views.handover_execute, name='handover_execute'),
    path('handover/history/', views.handover_history, name='handover_history'),

    # ============================================================
    # GRADUATION PROFILES
    # ============================================================
    path('graduation/', views.graduation_list, name='graduation_list'),
    path('graduation/<int:pk>/', views.graduation_detail, name='graduation_detail'),

    # ============================================================
    # DELEGATION
    # ============================================================
    path('delegation/', views.delegation_home, name='delegation_home'),

    # ============================================================
    # OFFICE & PERMISSION MANAGEMENT
    # ============================================================
    path('offices/', views.office_list, name='office_list'),
    path('offices/create/', views.office_create, name='office_create'),
    path('offices/<int:pk>/edit/', views.office_edit, name='office_edit'),
    path('offices/<int:pk>/delete/', views.office_delete, name='office_delete'),
    path('offices/<int:pk>/permissions/', views.office_permissions, name='office_permissions'),
    path('assignments/', views.user_office_assignment, name='user_office_assignment'),
    path('assignments/user/<int:user_id>/', views.user_office_assignment, name='user_office_assignment_for'),
    path('assignments/<int:pk>/unassign/', views.user_office_unassign, name='user_office_unassign'),

    # ============================================================
    # USER MANAGEMENT (super admin)
    # ============================================================
    path('users/', views.user_list, name='user_list'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:pk>/delete/', views.user_delete, name='user_delete'),

    # ============================================================
    # GROUP MANAGEMENT
    # ============================================================
    path('groups/', views.group_list, name='group_list'),
    path('groups/create/', views.group_form, name='group_create'),
    path('groups/<int:pk>/edit/', views.group_form, name='group_edit'),
    path('groups/<int:pk>/permissions/', views.group_permissions, name='group_permissions'),
    path('groups/<int:pk>/delete/', views.group_delete, name='group_delete'),

    # ============================================================
    # GRADUATION PROFILES (alumni directory + self-edit)
    # ============================================================
    path('alumni/', views.graduation_list, name='graduation_list'),
    path('alumni/me/', views.my_graduation_profile, name='my_graduation_profile'),
    path('alumni/<int:pk>/', views.graduation_detail, name='graduation_detail'),
    path('alumni/<int:pk>/edit/', views.graduation_edit, name='graduation_edit'),
    path('alumni/<int:pk>/delete/', views.graduation_delete, name='graduation_delete'),

    # ============================================================
    # SESSION DOCUMENTS (magazine / archive)
    # ============================================================
    path('sessions/', views.session_document_list, name='session_document_list'),
    path('sessions/manage/', views.session_document_manage, name='session_document_manage'),
    path('sessions/new/', views.session_document_form, name='session_document_create'),
    path('sessions/<int:pk>/', views.session_document_detail, name='session_document_detail'),
    path('sessions/<int:pk>/edit/', views.session_document_form, name='session_document_edit'),
    path('sessions/<int:pk>/delete/', views.session_document_delete, name='session_document_delete'),
    path('sessions/<int:pk>/toggle-publish/', views.session_document_toggle_publish, name='session_document_toggle_publish'),


]