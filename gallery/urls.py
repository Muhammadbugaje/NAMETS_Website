from django.urls import path
from . import views

app_name = 'gallery'

urlpatterns = [
    path('', views.gallery_list, name='list'),
    path('<int:pk>/', views.gallery_detail, name='detail'),
]