from django.urls import path
from . import views

app_name = 'gallery'

urlpatterns = [
    # ===== PUBLIC VIEWS =====
    path('', views.gallery_list, name='list'),
    path('<int:pk>/', views.gallery_detail, name='detail'),

    # ===== ADMIN/EXCO VIEWS =====
    path('admin/', views.admin_gallery_list, name='admin_gallery_list'),
    path('admin/create/', views.admin_gallery_create, name='admin_gallery_create'),
    path('admin/<int:pk>/edit/', views.admin_gallery_edit, name='admin_gallery_edit'),
    path('admin/<int:pk>/delete/', views.admin_gallery_delete, name='admin_gallery_delete'),
]