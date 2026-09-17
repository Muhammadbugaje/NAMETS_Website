from django.urls import path
from . import views

app_name = 'community'

urlpatterns = [
    # ===== PUBLIC VIEWS =====
    path('patrons/', views.patron_list, name='patron_list'),
    path('patrons/<slug:slug>/', views.patron_detail, name='patron_detail'),
    path('executives/', views.executive_list, name='executive_list'),
    path('questions/', views.question_list, name='question_list'),
    path('ask/', views.ask_question, name='ask_question'),
    path('about/', views.about_page, name='about'),
    path('developers/', views.developer_list, name='developer_list'),
    path('apply/tutor/', views.tutor_application, name='tutor_apply'),
    path('apply/membership/', views.membership_application, name='membership_apply'),

    # ===== ADMIN/EXCO VIEWS =====
    # Patrons
    path('admin/patrons/', views.admin_patron_list, name='admin_patron_list'),
    path('admin/patrons/create/', views.admin_patron_create, name='admin_patron_create'),
    path('admin/patrons/<int:pk>/edit/', views.admin_patron_edit, name='admin_patron_edit'),
    path('admin/patrons/<int:pk>/delete/', views.admin_patron_delete, name='admin_patron_delete'),

    # Executive Years
    path('admin/executive-years/', views.admin_executive_year_list, name='admin_executive_year_list'),
    path('admin/executive-years/create/', views.admin_executive_year_create, name='admin_executive_year_create'),
    path('admin/executive-years/<int:pk>/edit/', views.admin_executive_year_edit, name='admin_executive_year_edit'),
    path('admin/executive-years/<int:pk>/delete/', views.admin_executive_year_delete, name='admin_executive_year_delete'),

    # Executives
    path('admin/executives/', views.admin_executive_list, name='admin_executive_list'),
    path('admin/executives/create/', views.admin_executive_create, name='admin_executive_create'),
    path('admin/executives/<int:pk>/edit/', views.admin_executive_edit, name='admin_executive_edit'),
    path('admin/executives/<int:pk>/delete/', views.admin_executive_delete, name='admin_executive_delete'),

    path('admin/executives/export/', views.admin_executive_export, name='admin_executive_export'),
    path('admin/executive-year/create-ajax/', views.admin_executive_year_create_ajax, name='admin_executive_year_create_ajax'),

    # Developers
    path('admin/developers/', views.admin_developer_list, name='admin_developer_list'),
    path('admin/developers/create/', views.admin_developer_create, name='admin_developer_create'),
    path('admin/developers/<int:pk>/edit/', views.admin_developer_edit, name='admin_developer_edit'),
    path('admin/developers/<int:pk>/delete/', views.admin_developer_delete, name='admin_developer_delete'),

    # About Page
    path('admin/about/', views.admin_about_edit, name='admin_about_edit'),

    # Questions & Answers
    path('admin/questions/', views.admin_question_list, name='admin_question_list'),
    path('admin/questions/<int:pk>/answer/', views.admin_question_answer, name='admin_question_answer'),
    path('admin/questions/<int:pk>/delete/', views.admin_question_delete, name='admin_question_delete'),


    # ===== MEMBERSHIP APPLICATIONS ADMIN =====
    path('admin/membership-applications/', views.admin_membership_application_list, name='admin_membership_application_list'),
    path('admin/membership-applications/create/', views.admin_membership_application_create, name='admin_membership_application_create'),
    path('admin/membership-applications/<int:pk>/', views.admin_membership_application_detail, name='admin_membership_application_detail'),
    path('admin/membership-applications/<int:pk>/edit/', views.admin_membership_application_edit, name='admin_membership_application_edit'),
    path('admin/membership-applications/<int:pk>/delete/', views.admin_membership_application_delete, name='admin_membership_application_delete'),
    path('admin/membership-applications/export/', views.admin_membership_application_export, name='admin_membership_application_export'),

    # tutors applications import and export
    path('admin/tutor-applications/', views.admin_tutor_application_list, name='admin_tutor_application_list'),
    path('admin/tutor-applications/create/', views.admin_tutor_application_create, name='admin_tutor_application_create'),
    path('admin/tutor-applications/<int:pk>/', views.admin_tutor_application_detail, name='admin_tutor_application_detail'),
    path('admin/tutor-applications/<int:pk>/edit/', views.admin_tutor_application_edit, name='admin_tutor_application_edit'),
    path('admin/tutor-applications/<int:pk>/delete/', views.admin_tutor_application_delete, name='admin_tutor_application_delete'),
    path('admin/tutor-applications/export/', views.admin_tutor_application_export, name='admin_tutor_application_export'),


    path('admin/questions/<int:pk>/toggle/', views.admin_question_toggle, name='admin_question_toggle'),
    path('admin/executives/<int:pk>/toggle-public/', views.admin_executive_toggle_public, name='admin_executive_toggle_public'),

    # Skills
    path('admin/skills/', views.admin_skill_list, name='admin_skill_list'),
    path('admin/skills/create/', views.admin_skill_create, name='admin_skill_create'),
    path('admin/skills/<int:pk>/edit/', views.admin_skill_edit, name='admin_skill_edit'),
    path('admin/skills/<int:pk>/delete/', views.admin_skill_delete, name='admin_skill_delete'),

    # Contact Phones
    path('admin/contact-phones/', views.admin_contact_phone_list, name='admin_contact_phone_list'),
    path('admin/contact-phones/create/', views.admin_contact_phone_create, name='admin_contact_phone_create'),
    path('admin/contact-phones/<int:pk>/edit/', views.admin_contact_phone_edit, name='admin_contact_phone_edit'),
    path('admin/contact-phones/<int:pk>/delete/', views.admin_contact_phone_delete, name='admin_contact_phone_delete'),

    # Social Media Links
    path('admin/social-links/', views.admin_social_link_list, name='admin_social_link_list'),
    path('admin/social-links/create/', views.admin_social_link_create, name='admin_social_link_create'),
    path('admin/social-links/<int:pk>/edit/', views.admin_social_link_edit, name='admin_social_link_edit'),
    path('admin/social-links/<int:pk>/delete/', views.admin_social_link_delete, name='admin_social_link_delete'),

    # Documents
    path('admin/documents/', views.admin_document_list, name='admin_document_list'),
    path('admin/documents/create/', views.admin_document_create, name='admin_document_create'),
    path('admin/documents/<int:pk>/edit/', views.admin_document_edit, name='admin_document_edit'),
    path('admin/documents/<int:pk>/delete/', views.admin_document_delete, name='admin_document_delete'),



]