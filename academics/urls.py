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
    path('islamiyya/register/', views.islamiyya_register, name='islamiyya_register'),
    path('islamiyya/status/', views.islamiyya_check_status, name='islamiyya_check_status'),
    path('islamiyya/dashboard/', views.islamiyya_dashboard, name='islamiyya_dashboard'),
    path('resources/', views.resources_page, name='resources'),
    path('submit-resource/', views.submit_resource, name='submit_resource'),
    path('download/<int:pk>/', views.download_resource, name='download_resource'),
    path('competition-results/', views.competition_results, name='competition_results'),
]