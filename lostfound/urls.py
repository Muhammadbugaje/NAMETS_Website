
from django.urls import path
from . import views

app_name = 'lostfound'

urlpatterns = [
    # ===== PUBLIC VIEWS =====
    path('', views.item_list, name='list'),
    path('<int:pk>/', views.item_detail, name='detail'),

    # ===== ADMIN/EXCO VIEWS =====
    path('admin/', views.admin_item_list, name='admin_item_list'),
    path('admin/create/', views.admin_item_create, name='admin_item_create'),
    path('admin/<int:pk>/edit/', views.admin_item_edit, name='admin_item_edit'),
    path('admin/<int:pk>/delete/', views.admin_item_delete, name='admin_item_delete'),
    path('admin/<int:pk>/claim/', views.admin_item_mark_claimed, name='admin_item_mark_claimed'),
]