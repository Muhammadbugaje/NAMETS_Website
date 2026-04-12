from django.db.models import Count
from django.utils import timezone


def unread_count_badge(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return None
    count = request.user.namets_notifications.filter(is_read=False).count()
    return str(count) if count > 0 else None


def get_dashboard_stats(user):
    from communications.models import Announcement
    from events.models import Event
    from community.models import MembershipApplication, TutorApplication, Question
    from academics.models import IslamiyyaRegistration, UserResourceSubmission
    from lostfound.models import Item
    from gallery.models import Gallery, GalleryImage

    s = {}
    s["unread_notifications"] = user.namets_notifications.filter(is_read=False).count()

    if user.is_superuser or user.has_perm("communications.view_announcement"):
        s["announcements"] = Announcement.objects.count()
    if user.is_superuser or user.has_perm("events.view_event"):
        s["events"] = Event.objects.filter(start_datetime__date__gte=timezone.now().date()).count()
    if user.is_superuser or user.has_perm("community.view_membershipapplication"):
        s["membership_pending"] = MembershipApplication.objects.count()
    if user.is_superuser or user.has_perm("community.view_tutorapplication"):
        s["tutor_pending"] = TutorApplication.objects.count()
    if user.is_superuser or user.has_perm("academics.view_islamiyyaregistration"):
        s["islamiyya_unverified"] = IslamiyyaRegistration.objects.filter(is_verified=False).count()
    if user.is_superuser or user.has_perm("academics.view_resource"):
        s["pending_resources"] = UserResourceSubmission.objects.filter(status='pending').count()
    if user.is_superuser or user.has_perm("lostfound.view_item"):
        s["lost_items"] = Item.objects.count()
    if user.is_superuser or user.has_perm("gallery.view_gallery"):
        s["gallery_photos"] = GalleryImage.objects.count()
    if user.is_superuser or user.has_perm("community.view_question"):
        s["qa_questions"] = Question.objects.filter(is_public=False).count()
    return s


def get_chart_data(user):
    from django.db.models.functions import TruncDay
    from datetime import timedelta
    from communications.models import Announcement
    from events.models import Event

    end   = timezone.now()
    start = end - timedelta(days=30)
    labels = [(start + timedelta(days=i)).strftime("%b %d") for i in range(31)]

    def series(qs):
        m = {item["day"].strftime("%b %d"): item["count"] for item in qs}
        return [m.get(l, 0) for l in labels]

    ann = (Announcement.objects
           .filter(created_at__gte=start)
           .annotate(day=TruncDay("created_at"))
           .values("day").annotate(count=Count("id")).order_by("day")
           ) if (user.is_superuser or user.has_perm("communications.view_announcement")) else []

    evt = (Event.objects
           .filter(created_at__gte=start)
           .annotate(day=TruncDay("created_at"))
           .values("day").annotate(count=Count("id")).order_by("day")
           ) if (user.is_superuser or user.has_perm("events.view_event")) and hasattr(Event, "created_at") else []

    return {"labels": labels, "announcements": series(ann), "events": series(evt)}