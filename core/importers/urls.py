from django.urls import path
from . import views

app_name = 'importers'

urlpatterns = [
    path('<str:import_key>/template/', views.download_template, name='template'),
    path('<str:import_key>/upload/', views.upload_review, name='upload'),
    path('<str:import_key>/confirm/<uuid:token>/', views.confirm_import, name='confirm'),
    path('<str:import_key>/export/', views.export_view, name='export'),
]