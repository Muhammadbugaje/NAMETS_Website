from django.urls import path
from . import views

app_name = 'community'

urlpatterns = [
    path('patrons/', views.patron_list, name='patron_list'),
    path('executives/', views.executive_list, name='executive_list'),
    path('questions/', views.question_list, name='question_list'),
    path('ask/', views.ask_question, name='ask_question'),
    path('about/', views.about_page, name='about'),
    path('developers/', views.developer_list, name='developer_list'),
]