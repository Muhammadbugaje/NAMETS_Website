from django.urls import path
from . import views

app_name = "namets_notifications"

urlpatterns = [
    path("",                      views.dashboard,        name="dashboard"),
    path("inbox/",                views.inbox,            name="inbox"),
    path("activity/",             views.activity_log,     name="activity"),
    path("mark-read/<int:pk>/",   views.mark_read,        name="mark_read"),
    path("mark-all-read/",        views.mark_all_read,    name="mark_all_read"),
    path("api/unread-count/",     views.unread_count_api, name="unread_count"),
]