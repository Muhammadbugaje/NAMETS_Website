from django.urls import path
from . import views
from . import views_hero

app_name = 'core'

urlpatterns = [
    path("health/", views.health_check, name="health_check"),
    path('', views.homepage, name='homepage'),
    path('settings/', views.site_settings_view, name='site_settings'),
    # ============================================================
    # HERO SLIDES (EXCO admin)
    # ============================================================
    path('admin/hero-slides/', views_hero.hero_slide_list, name='hero_slide_list'),
    path('admin/hero-slides/new/', views_hero.hero_slide_form, name='hero_slide_create'),
    path('admin/hero-slides/<int:pk>/edit/', views_hero.hero_slide_form, name='hero_slide_edit'),
    path('admin/hero-slides/<int:pk>/delete/', views_hero.hero_slide_delete, name='hero_slide_delete'),
    path('admin/hero-slides/<int:pk>/toggle/', views_hero.hero_slide_toggle, name='hero_slide_toggle'),
]