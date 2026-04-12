import json
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .models import ActivityLog, Notification
from .utils import get_chart_data, get_dashboard_stats


@staff_member_required
def dashboard(request):
    return render(request, "namets_notifications/dashboard.html", {
        "title": "Dashboard",
        "stats": get_dashboard_stats(request.user),
        "chart_data": json.dumps(get_chart_data(request.user)),
        "recent_activity": ActivityLog.objects.select_related("user")[:15],
        "recent_notifications": request.user.namets_notifications.select_related("recipient")[:5],
    })


@staff_member_required
def inbox(request):
    filter_type = request.GET.get("type", "all")
    qs = request.user.namets_notifications.all()
    if filter_type != "all":
        qs = qs.filter(notification_type=filter_type)
    return render(request, "namets_notifications/inbox.html", {
        "title": "Notifications",
        "notifications": qs[:100],
        "unread_count": request.user.namets_notifications.filter(is_read=False).count(),
        "notification_types": Notification.Type.choices,
        "current_filter": filter_type,
    })


@require_POST
@staff_member_required
def mark_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notif.mark_read()
    return redirect(notif.admin_link or request.POST.get("next", "/admin/"))


@require_POST
@staff_member_required
def mark_all_read(request):
    request.user.namets_notifications.filter(is_read=False).update(is_read=True)
    return redirect("namets_notifications:inbox")


@staff_member_required
def activity_log(request):
    return render(request, "namets_notifications/activity.html", {
        "title": "Activity Log",
        "logs": ActivityLog.objects.select_related("user")[:200],
    })


@staff_member_required
def unread_count_api(request):
    return JsonResponse({"count": request.user.namets_notifications.filter(is_read=False).count()})