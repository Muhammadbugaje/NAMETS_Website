from django.urls import path
from . import views

app_name = 'academics'

urlpatterns = [
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
]