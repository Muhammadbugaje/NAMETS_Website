from django.urls import path
from . import views

app_name = 'lostfound'

urlpatterns = [
    path('', views.item_list, name='list'),
    path('item/<int:pk>/', views.item_detail, name='detail'),
]