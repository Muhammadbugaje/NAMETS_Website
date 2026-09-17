from django.urls import path

from . import views
from . import views_admin

app_name = 'communications'

urlpatterns = [
    # ===== PUBLIC VIEWS =====
    path('announcements/', views.announcement_list, name='announcement_list'),
    path('announcements/<slug:slug>/', views.announcement_detail, name='announcement_detail'),
    path('prayer-times/', views.prayer_times, name='prayer_times'),
    path('donations/', views.donation_list, name='donation_list'),
    path('mosque/', views.mosque_info, name='mosque_info'),
    path('subscribe/', views.subscribe, name='subscribe'),
    path('subscribe/success/', views.subscribe_success, name='subscribe_success'),
    path('unsubscribe/<uuid:token>/', views.unsubscribe, name='unsubscribe'),
    path('unsubscribe/', views.unsubscribe_by_email, name='unsubscribe_by_email'),
    path('confirm-subscription/', views.confirm_subscription, name='confirm_subscription'),
    path('article/', views.article_list, name='article_list'),
    path('article/<slug:slug>/', views.article_detail, name='article_detail'),
    path('magazine/', views.magazine_list, name='magazine_list'),
    path('magazine/<slug:slug>/', views.magazine_detail, name='magazine_detail'),

    # ===== ANNOUNCEMENT ADMIN =====
    path('admin/announcements/', views.announcement_admin_list, name='announcement_admin_list'),
    path('admin/announcements/create/', views.announcement_create, name='announcement_create'),
    path('admin/announcements/<slug:slug>/edit/', views.announcement_edit, name='announcement_edit'),
    path('admin/announcements/<slug:slug>/delete/', views.announcement_delete, name='announcement_delete'),
    path('admin/announcements/ai-draft/', views.ai_draft_announcement, name='ai_draft_announcement'),

    # ===== PRAYER TIMES ADMIN =====
    path('admin/prayer/', views.admin_prayer_list, name='admin_prayer_list'),
    path('admin/prayer/create/', views.admin_prayer_create, name='admin_prayer_create'),
    path('admin/prayer/<int:pk>/edit/', views.admin_prayer_edit, name='admin_prayer_edit'),
    path('admin/prayer/<int:pk>/delete/', views.admin_prayer_delete, name='admin_prayer_delete'),

    # ===== DONATION CAMPAIGNS ADMIN =====
    path('admin/donations/', views.admin_donation_list, name='admin_donation_list'),
    path('admin/donations/create/', views.admin_donation_create, name='admin_donation_create'),
    path('admin/donations/<int:pk>/edit/', views.admin_donation_edit, name='admin_donation_edit'),
    path('admin/donations/<int:pk>/delete/', views.admin_donation_delete, name='admin_donation_delete'),

    # ===== MOSQUE INFO & RULES ADMIN =====
    path('admin/mosque/', views.admin_mosque_edit, name='admin_mosque_edit'),
    path('admin/mosque/rules/', views.admin_mosque_rule_list, name='admin_mosque_rule_list'),
    path('admin/mosque/rules/create/', views.admin_mosque_rule_create, name='admin_mosque_rule_create'),
    path('admin/mosque/rules/<int:pk>/edit/', views.admin_mosque_rule_edit, name='admin_mosque_rule_edit'),
    path('admin/mosque/rules/<int:pk>/delete/', views.admin_mosque_rule_delete, name='admin_mosque_rule_delete'),

    # ===== MAGAZINE ISSUES ADMIN =====
    path('admin/magazines/', views.admin_magazine_list, name='admin_magazine_list'),
    path('admin/magazines/create/', views.admin_magazine_create, name='admin_magazine_create'),
    path('admin/magazines/<slug:slug>/edit/', views.admin_magazine_edit, name='admin_magazine_edit'),
    path('admin/magazines/<slug:slug>/delete/', views.admin_magazine_delete, name='admin_magazine_delete'),

    # ===== ARTICLES ADMIN =====
    path('admin/articles/', views.admin_article_list, name='admin_article_list'),
    path('admin/articles/create/', views.admin_article_create, name='admin_article_create'),
    path('admin/articles/<slug:slug>/edit/', views.admin_article_edit, name='admin_article_edit'),
    path('admin/articles/<slug:slug>/delete/', views.admin_article_delete, name='admin_article_delete'),

    # ===== SUBSCRIBERS ADMIN =====
    path('admin/subscribers/', views.admin_subscriber_list, name='admin_subscriber_list'),
    path('admin/subscribers/export/', views.admin_subscriber_export, name='admin_subscriber_export'),

    # ===== BROADCAST =====
    path('admin/broadcast/', views.admin_broadcast, name='admin_broadcast'),
    
    path('admin/subscribers/create/', views.admin_subscriber_create, name='admin_subscriber_create'),
    path('admin/subscribers/<int:pk>/edit/', views.admin_subscriber_edit, name='admin_subscriber_edit'),
    path('admin/subscribers/<int:pk>/delete/', views.admin_subscriber_delete, name='admin_subscriber_delete'),    
    
]